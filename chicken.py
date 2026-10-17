import chicken_updates
import chicken_storage
import json, os, re, sys, time, threading, queue, ctypes, math, subprocess, traceback, uuid
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import winsound
from pynput import mouse, keyboard
for _fn in (lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2), lambda: ctypes.windll.winmm.timeBeginPeriod(1)):
    try:
        _fn()
    except Exception:
        pass
RESOURCE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'Chicken')
os.makedirs(HERE, exist_ok=True)
CFG = os.path.join(HERE, 'chicken_settings.json')
MACROS = os.path.join(HERE, 'macros.json')
LAST = os.path.join(HERE, 'chicken_last_macro.json')
DEFAULT_HOT = {'rec': 'f8', 'play': 'f9', 'stop': 'f10', 'toggle': 'home'}
LABELS = {'rec': 'Record', 'play': 'Play', 'stop': 'Stop', 'toggle': 'Disable/Enable'}
DEFAULTS = {'sounds': True, 'always_on_top': True, 'precise_timing': True, 'loop_delay_ms': 0, 'start_delay_s': 0.0, 'trim_first_delay': True, 'record_move': False, 'move_interval_ms': 30, 'setup_done': False, 'geometry': '', 'skip_ctrl_warning': False, 'admin_on_start': False, 'hide_admin_prompt': False, 'macro_folder': '', 'check_updates_on_start': True}
INT_KEYS = {'loop_delay_ms', 'move_interval_ms'}
FLOAT_KEYS = {'start_delay_s'}
GEOM_RE = re.compile('(\\d+)x(\\d+)([+-]-?\\d+)([+-]-?\\d+)')
DEFAULT_SIZE = (780, 430)
MIN_SIZE = (640, 360)
BG, CARD, CARD2, HOVER = ('#101318', '#191f28', '#252e3a', '#344253')
TXT, MUTED = ('#edf2fa', '#9baabe')
GREEN, GREEN_H = ('#2e8b57', '#3fb950')
RED, RED_H = ('#b3362c', '#e5484d')
BLUE, ORANGE = ('#4c8dff', '#f0a030')
FONT = ('Segoe UI', 9)
FONT_B = ('Segoe UI', 9, 'bold')
SMALL = ('Segoe UI', 8)
TYPE_COLOR = {'KEY': '#7cc4ff', 'MOUSE': '#ffb454', 'MOVE': '#8bd5a0', 'SCROLL': '#c3a6ff', 'WAIT': '#f0d264'}
MOD_ORDER = ('ctrl', 'alt', 'shift', 'cmd')
MOD_ALIASES = {'ctrl': 'ctrl', 'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl', 'shift': 'shift', 'shift_l': 'shift', 'shift_r': 'shift', 'alt': 'alt', 'alt_l': 'alt', 'alt_r': 'alt', 'alt_gr': 'alt', 'cmd': 'cmd', 'cmd_l': 'cmd', 'cmd_r': 'cmd'}
MOD_PREFIXES = ('ctrl', 'shift', 'alt', 'cmd')

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def mod_name(key):
    if isinstance(key, keyboard.Key):
        return MOD_ALIASES.get(key.name)
    return None

def key_name(key):
    if isinstance(key, keyboard.Key):
        return key.name
    vk = getattr(key, 'vk', None)
    if vk is not None:
        if 65 <= vk <= 90:
            return chr(vk).lower()
        if 48 <= vk <= 57:
            return chr(vk)
        if 96 <= vk <= 105:
            return f'num{vk - 96}'
    ch = getattr(key, 'char', None)
    if ch and ch.isprintable():
        return ch.lower()
    return f'vk{vk}'

def make_combo(mods, name):
    return '+'.join([m for m in MOD_ORDER if m in mods] + [name])

def pretty_combo(combo):
    if not combo:
        return 'Not assigned'
    return ' + '.join((p.upper() if len(p) <= 3 else p.capitalize() for p in combo.split('+')))

def is_modifier_action(a):
    return a.get('t') == 'key' and str(a.get('k', '')).startswith(MOD_PREFIXES)

def action_key_id(a):
    return a.get('k') or a.get('vk') or a.get('c')

def finalize_actions(actions, trim_first):
    """Safety net: remove key events caused by the start/stop shortcut itself."""
    out, held, carry = ([], {}, 0.0)
    for a in actions:
        a = dict(a)
        a['d'] = round(a['d'] + carry, 4)
        carry = 0.0
        if a['t'] == 'key':
            kid = action_key_id(a)
            if a['p']:
                held[kid] = len(out)
            elif kid in held:
                del held[kid]
            else:
                carry = a['d']
                continue
        out.append(a)
    remove = set()
    for kid, idx in held.items():
        if is_modifier_action(out[idx]):
            remove.add(idx)
        else:
            out.append({'t': 'key', **{k: v for k, v in out[idx].items() if k in ('k', 'c', 'vk')}, 'p': False, 'd': 0.0})
    out = [a for i, a in enumerate(out) if i not in remove]
    if out and trim_first:
        out[0]['d'] = 0.0
    return out

def validate_actions(data):
    if not isinstance(data, list):
        raise ValueError('A macro must be a JSON list.')
    for i, a in enumerate(data, 1):
        if not isinstance(a, dict) or a.get('t') not in ('move', 'click', 'scroll', 'key', 'wait'):
            raise ValueError(f'Invalid action {i}.')
        d = a.get('d')
        if type(d) not in (int, float) or not math.isfinite(d) or d < 0:
            raise ValueError(f'Invalid delay at action {i}.')
        t = a['t']
        if t in ('move', 'click', 'scroll') and any((type(a.get(k)) is not int for k in ('x', 'y'))):
            raise ValueError(f'Invalid coordinates at action {i}.')
        if t in ('click', 'key') and type(a.get('p')) is not bool:
            raise ValueError(f'Invalid press state at action {i}.')
        if t == 'click' and a.get('b') not in mouse.Button.__members__:
            raise ValueError(f'Invalid mouse button at action {i}.')
        if t == 'scroll' and any((type(a.get(k)) is not int for k in ('dx', 'dy'))):
            raise ValueError(f'Invalid scroll at action {i}.')
        if t == 'key':
            if 'k' in a:
                if a['k'] not in keyboard.Key.__members__:
                    raise ValueError(f'Invalid key at action {i}.')
            elif not (type(a.get('vk')) is int or (isinstance(a.get('c'), str) and len(a['c']) == 1)):
                raise ValueError(f'Invalid key at action {i}.')
    return data

def new_macro(name, actions=None):
    return {'id': uuid.uuid4().hex[:8], 'name': name, 'bind': '', 'actions': actions or [], 'repeat': 1, 'speed': 1.0, 'loop': False}

def clean_macro(m):
    if not isinstance(m, dict):
        raise ValueError('bad macro')
    out = new_macro(str(m.get('name', 'Macro'))[:40] or 'Macro', validate_actions(m.get('actions', [])))
    if isinstance(m.get('id'), str) and m['id']:
        out['id'] = m['id']
    if isinstance(m.get('bind'), str):
        out['bind'] = m['bind'].lower()
    if type(m.get('repeat')) is int and 1 <= m['repeat'] <= 9999:
        out['repeat'] = m['repeat']
    if type(m.get('speed')) in (int, float) and math.isfinite(m['speed']) and (0.1 <= m['speed'] <= 10):
        out['speed'] = float(m['speed'])
    out['loop'] = m.get('loop') is True
    return out

def describe_action(a, i):
    t = a['t']
    if t == 'wait':
        kind, desc = ('WAIT', 'Pause')
    elif t == 'click':
        kind, desc = ('MOUSE', f"{a['b'].capitalize()} {('down' if a['p'] else 'up')}  ({a['x']}, {a['y']})")
    elif t == 'move':
        kind, desc = ('MOVE', f"to ({a['x']}, {a['y']})")
    elif t == 'scroll':
        kind, desc = ('SCROLL', f"({a['dx']}, {a['dy']})")
    else:
        name = a.get('k') or a.get('c')
        if not name:
            vk = a.get('vk')
            name = chr(vk).lower() if isinstance(vk, int) and 65 <= vk <= 90 else f'vk{vk}'
        kind, desc = ('KEY', f"{name}  {('down' if a['p'] else 'up')}")
    return (kind, f"{i + 1:>3}  {kind:<7}{a['d'] * 1000:>9.1f} ms  {desc}")

def mkbtn(parent, text, cmd, bg=CARD2, hover=HOVER, fg=TXT, font=FONT, **kw):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=hover, activeforeground=fg, relief='flat', bd=0, cursor='hand2', font=font, **kw)
    b.bind('<Enter>', lambda e: b.config(bg=hover))
    b.bind('<Leave>', lambda e: b.config(bg=bg))
    return b

class App:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Chicken')
        self.root.minsize(*MIN_SIZE)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close_app)
        self.apply_icon(self.root)
        self.opt = dict(DEFAULTS)
        self.hot = dict(DEFAULT_HOT)
        self.load_cfg()
        self.root.attributes('-topmost', self.opt['always_on_top'])
        self.restore_geometry()
        self.admin = is_admin()
        self.enabled = True
        self.macros = []
        self.cur = None
        self.recording = False
        self.playing = False
        self.playing_id = None
        self.stop_flag = False
        self.stop_sound_sent = False
        self.last_t = 0.0
        self.last_move = 0.0
        self.record_lock = threading.RLock()
        self.mods = set()
        self.pending = []
        self.ignore_up = set()
        self.down = set()
        self.suppressed = set()
        self.capturing = False
        self.cap_win = None
        self.cap_cb = None
        self.cap_label = None
        self.cap_owner = None
        self.loading = False
        self.rects = {}
        self.sw = None
        self.v = {}
        self.hk_btns = {}
        self.q = queue.Queue()
        self.mctl = mouse.Controller()
        self.kctl = keyboard.Controller()
        self.build_home()
        self.build_editor()
        self.load_macros()
        self.refresh_home()
        self.show_home()
        self.mouse_listener = mouse.Listener(on_click=self.on_click, on_scroll=self.on_scroll, on_move=self.on_move)
        self.mouse_listener.start()
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release, win32_event_filter=self.windows_key_filter)
        self.keyboard_listener.start()
        self.root.after(50, self.poll)
        self.root.after(250, self.first_run)
        self.root.after(4000, self.startup_update_check)
        self.root.mainloop()

    @property
    def actions(self):
        return self.cur['actions'] if self.cur else []

    def apply_icon(self, window):
        try:
            window.iconbitmap(os.path.join(RESOURCE, 'chicken.ico'))
        except tk.TclError:
            pass

    def restore_geometry(self, reset=False):
        sw, sh = (self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        m = None if reset else GEOM_RE.fullmatch(self.opt.get('geometry', ''))
        if m:
            w, h, x, y = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        else:
            (w, h), x, y = (DEFAULT_SIZE, 40, 40)
        w = max(MIN_SIZE[0], min(w, sw))
        h = max(MIN_SIZE[1], min(h, sh))
        x = max(0, min(x, sw - 120))
        y = max(0, min(y, sh - 120))
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    def load_cfg(self):
        try:
            with open(CFG, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        for k, default in DEFAULTS.items():
            value = data.get(k)
            if k == 'macro_folder':
                if isinstance(value, str):
                    self.opt[k] = value
                continue
            if k == 'geometry':
                if isinstance(value, str) and GEOM_RE.fullmatch(value):
                    self.opt[k] = value
                continue
            if type(default) is bool and type(value) is bool:
                self.opt[k] = value
            elif type(default) in (int, float) and type(value) in (int, float) and (type(value) is not bool) and math.isfinite(value) and (value >= 0):
                self.opt[k] = int(value) if type(default) is int else float(value)
        self.opt['move_interval_ms'] = max(5, self.opt['move_interval_ms'])
        h = data.get('hotkeys')
        if isinstance(h, dict):
            merged = dict(DEFAULT_HOT)
            merged.update({k: v.lower() for k, v in h.items() if k in DEFAULT_HOT and isinstance(v, str) and v})
            if len(set(merged.values())) == 4:
                self.hot = merged

    def write_json(self, path, data, **kw):
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, **kw)
        os.replace(tmp, path)

    def save_cfg(self):
        if not getattr(self, '_allow_saves', True):
            return
        try:
            self.write_json(CFG, {**self.opt, 'hotkeys': self.hot}, indent=1)
        except OSError as e:
            messagebox.showerror('Could not save settings', str(e), parent=self.root)

    def hk(self, name):
        return pretty_combo(self.hot[name])

    def sound(self, name):
        if not self.opt['sounds']:
            return
        try:
            winsound.PlaySound(os.path.join(RESOURCE, 'sounds', name + '.wav'), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError:
            pass

    def first_run(self):
        if self.opt['setup_done']:
            self.root.after(100, self.startup_admin)
            return
        w = tk.Toplevel(self.root)
        w.title('Welcome to Chicken')
        w.configure(bg=BG)
        w.geometry('460x250+300+120')
        w.resizable(False, False)
        w.transient(self.root)
        self.apply_icon(w)
        w.attributes('-topmost', True)
        tk.Label(w, text='Quick setup', bg=BG, fg=TXT, font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=20, pady=(16, 4))
        var = tk.BooleanVar(value=self.opt['always_on_top'])
        tk.Checkbutton(w, text='Keep Chicken above other windows', variable=var, bg=BG, fg=TXT, selectcolor=CARD2, activebackground=BG, activeforeground=TXT, font=FONT_B, bd=0, highlightthickness=0).pack(anchor='w', padx=16, pady=6)
        tk.Label(w, text='Chicken stays above your other windows so you can watch\nand control macros while using another app.\nFullscreen games may hide it; borderless mode works better.\nYou can change this later in Settings > Interface.', bg=BG, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=20)

        def done():
            self.opt['always_on_top'] = var.get()
            self.opt['setup_done'] = True
            self.root.attributes('-topmost', self.opt['always_on_top'])
            self.save_cfg()
            w.destroy()
            self.root.after(100, self.startup_admin)
        w.protocol('WM_DELETE_WINDOW', done)
        mkbtn(w, 'Continue', done, bg=GREEN, hover=GREEN_H, font=FONT_B, padx=18, pady=5).pack(anchor='e', padx=20, pady=14)

    def build_home(self):
        self.home = tk.Frame(self.root, bg=BG)
        head = tk.Frame(self.home, bg=BG)
        head.pack(fill='x', padx=10, pady=(8, 6))
        tk.Label(head, text='CHICKEN', bg=BG, fg=TXT, font=('Segoe UI', 13, 'bold')).pack(side='left')
        tk.Label(head, text='  /  MACRO STUDIO', bg=BG, fg=MUTED, font=SMALL).pack(side='left', pady=(4, 0))
        mkbtn(head, 'Settings', self.open_settings, padx=10, pady=3).pack(side='right')
        self.home_status = tk.Label(head, text='● Ready', bg=BG, fg=GREEN_H, font=FONT_B)
        self.home_status.pack(side='right', padx=10)
        foot = tk.Frame(self.home, bg=BG)
        foot.pack(side='bottom', fill='x', padx=10, pady=(4, 8))
        self.home_toggle = mkbtn(foot, '', self.toggle_system, pady=5)
        self.home_toggle.pack(side='left', fill='x', expand=True)
        self.home_stop = mkbtn(foot, '', self.stop, pady=5)
        self.home_stop.pack(side='left', fill='x', expand=True, padx=(6, 0))
        card = tk.Frame(self.home, bg=CARD)
        card.pack(fill='both', expand=True, padx=10, pady=(0, 4))
        bar = tk.Frame(card, bg=CARD)
        bar.pack(fill='x', padx=8, pady=(6, 4))
        tk.Label(bar, text='YOUR MACROS', bg=CARD, fg=TXT, font=FONT_B).pack(side='left')
        mkbtn(bar, '+ Add macro', self.add_macro, bg=GREEN, hover=GREEN_H, font=FONT_B, padx=10, pady=3).pack(side='right')
        for text, cmd in (('Delete', self.delete_macro), ('Clear shortcut', self.clear_bind), ('Set shortcut', self.bind_selected), ('Duplicate', self.duplicate_macro), ('Rename', self.rename_macro), ('Open', self.open_selected)):
            mkbtn(bar, text, cmd, padx=7, pady=3).pack(side='right', padx=(0, 3))
        tk.Label(card, text='  NAME                                  BIND                 ACTIONS', bg=CARD2, fg=MUTED, font=('Consolas', 8), anchor='w', pady=3).pack(fill='x', padx=8)
        tk.Label(card, text='Double-click a macro to edit it. Use its shortcut to play it from another app.', bg=CARD, fg=MUTED, font=SMALL, anchor='w').pack(side='bottom', fill='x', padx=8, pady=(2, 5))
        self.mlist = tk.Listbox(card, bg=CARD, fg=TXT, font=('Consolas', 10), bd=0, highlightthickness=0, activestyle='none', selectbackground='#304c6b', selectforeground='white', exportselection=False)
        self.mlist.pack(fill='both', expand=True, padx=8, pady=(2, 2))
        self.mlist.bind('<Double-Button-1>', lambda e: self.open_selected())

    def refresh_home(self, select=None):
        self.mlist.delete(0, 'end')
        for m in self.macros:
            self.mlist.insert('end', f" {m['name'][:34]:<36}{(pretty_combo(m['bind']) if m['bind'] else '-'):<21}{len(m['actions'])}")
        if select is not None and 0 <= select < len(self.macros):
            self.mlist.selection_set(select)
        self.home_toggle.config(text=f"{('Disable' if self.enabled else 'Enable')} hotkeys [{self.hk('toggle')}]")
        self.home_stop.config(text=f"■ Stop [{self.hk('stop')}]")

    def selected_macro(self):
        sel = self.mlist.curselection()
        if not sel:
            messagebox.showinfo('Chicken', 'Select a macro, then choose an action.', parent=self.root)
            return None
        return self.macros[sel[0]]

    def busy(self):
        if self.recording or self.playing:
            messagebox.showinfo('Chicken', 'Stop the recording or playback before making this change.', parent=self.root)
            return True
        return False

    def add_macro(self):
        if self.busy():
            return
        name = simpledialog.askstring('New macro', 'Macro name:', initialvalue=f'Macro {len(self.macros) + 1}', parent=self.root)
        if name is None:
            return
        m = new_macro(name.strip()[:40] or f'Macro {len(self.macros) + 1}')
        self.macros.append(m)
        self.save_macros()
        self.open_macro(m)

    def open_selected(self):
        m = self.selected_macro()
        if m and (not self.busy()):
            self.open_macro(m)

    def rename_macro(self):
        m = self.selected_macro()
        if not m:
            return
        name = simpledialog.askstring('Rename macro', 'Macro name:', initialvalue=m['name'], parent=self.root)
        if name and name.strip():
            m['name'] = name.strip()[:40]
            self.save_macros()
            self.refresh_home(self.macros.index(m))

    def duplicate_macro(self):
        m = self.selected_macro()
        if not m or self.busy():
            return
        c = json.loads(json.dumps(m))
        c['id'] = uuid.uuid4().hex[:8]
        c['name'] = (m['name'] + ' copy')[:40]
        c['bind'] = ''
        self.macros.append(c)
        self.save_macros()
        self.refresh_home(len(self.macros) - 1)

    def delete_macro(self):
        m = self.selected_macro()
        if not m or self.busy():
            return
        if messagebox.askyesno('Delete macro', f"Delete '{m['name']}'?", parent=self.root):
            self.macros.remove(m)
            self.save_macros()
            self.refresh_home()

    def bind_selected(self):
        m = self.selected_macro()
        if m:
            self.ask_bind(f"Bind for '{m['name']}'", lambda combo: self.set_macro_bind(m, combo), owner=m['bind'])

    def clear_bind(self):
        m = self.selected_macro()
        if m:
            m['bind'] = ''
            self.save_macros()
            self.refresh_home(self.macros.index(m))

    def set_macro_bind(self, m, combo):
        m['bind'] = combo
        self.save_macros()
        self.refresh_home(self.macros.index(m) if m in self.macros else None)
        if self.cur is m:
            self.bind_lbl.config(text=f'Shortcut: {pretty_combo(combo)}')

    def build_editor(self):
        self.editor = tk.Frame(self.root, bg=BG)
        header = tk.Frame(self.editor, bg=BG)
        header.pack(fill='x', padx=10, pady=(8, 6))
        mkbtn(header, '← Macros', self.go_home, padx=8, pady=3).pack(side='left')
        self.title_lbl = tk.Label(header, text='', bg=BG, fg=TXT, font=('Segoe UI', 12, 'bold'))
        self.title_lbl.pack(side='left', padx=10)
        mkbtn(header, 'Settings', self.open_settings, padx=10, pady=3).pack(side='right')
        self.status = tk.Label(header, text='● Ready', bg=BG, fg=GREEN_H, font=FONT_B)
        self.status.pack(side='right', padx=10)
        footer = tk.Frame(self.editor, bg=BG)
        footer.pack(side='bottom', fill='x', padx=10, pady=(4, 8))
        self.btn_rec = mkbtn(footer, '', self.toggle_rec, bg=RED, hover=RED_H, font=FONT_B, pady=5)
        self.btn_play = mkbtn(footer, '', self.play_current, bg=GREEN, hover=GREEN_H, font=FONT_B, pady=5)
        self.btn_stop = mkbtn(footer, '', self.stop, font=FONT_B, pady=5)
        self.btn_toggle = mkbtn(footer, '', self.toggle_system, pady=5)
        for i, b in enumerate((self.btn_rec, self.btn_play, self.btn_stop, self.btn_toggle)):
            footer.columnconfigure(i, weight=1)
            b.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 4, 0))
        body = tk.Frame(self.editor, bg=BG)
        body.pack(fill='both', expand=True, padx=10)
        left = tk.Frame(body, bg=CARD, width=200)
        left.pack(side='left', fill='y', padx=(0, 6))
        left.pack_propagate(False)

        def label(text):
            tk.Label(left, text=text, bg=CARD, fg=MUTED, font=('Segoe UI', 8, 'bold'), anchor='w').pack(fill='x', padx=10, pady=(7, 2))

        def check(text, var, cmd=None):
            tk.Checkbutton(left, text=text, variable=var, command=cmd, bg=CARD, fg=TXT, selectcolor=CARD2, activebackground=CARD, activeforeground=TXT, font=FONT, bd=0, highlightthickness=0).pack(anchor='w', padx=6)
        label('PLAY SHORTCUT')
        brow = tk.Frame(left, bg=CARD)
        brow.pack(fill='x', padx=10)
        self.bind_lbl = tk.Label(brow, text='Shortcut: Not set', bg=CARD, fg=TXT, font=FONT_B, anchor='w')
        self.bind_lbl.pack(side='left')
        mkbtn(brow, 'Clear', self.clear_current_bind, padx=6, pady=1).pack(side='right')
        mkbtn(brow, 'Set', self.bind_current, padx=8, pady=1).pack(side='right', padx=3)
        label('PLAYBACK')
        self.rep_v = tk.StringVar(value='1')
        self.spd_v = tk.StringVar(value='1.0')
        self.inf_v = tk.BooleanVar(value=False)
        for title, var, lo, hi, inc in (('Repeat', self.rep_v, 1, 9999, 1), ('Speed ×', self.spd_v, 0.1, 10, 0.1)):
            row = tk.Frame(left, bg=CARD)
            row.pack(fill='x', padx=10, pady=1)
            tk.Label(row, text=title, bg=CARD, fg=TXT, font=FONT).pack(side='left')
            self.spin(row, var, lo, hi, inc, 7).pack(side='right', ipady=1)
        check('Loop until stopped', self.inf_v)
        tk.Label(left, text='1.0× = original speed', bg=CARD, fg=MUTED, font=SMALL).pack(anchor='w', padx=10)
        for var in (self.rep_v, self.spd_v, self.inf_v):
            var.trace_add('write', lambda *a: self.sync_macro_opts())
        label('RECORDING & SOUND')
        self.move_v = tk.BooleanVar(value=self.opt['record_move'])
        check('Record mouse movements', self.move_v, self.main_options)
        self.sound_v = tk.BooleanVar(value=self.opt['sounds'])
        check('Play status sounds', self.sound_v, self.main_options)
        tk.Label(left, text='1,000 ms = 1 second', bg=CARD, fg=MUTED, font=SMALL).pack(anchor='w', padx=10, pady=(6, 0))
        right = tk.Frame(body, bg=CARD)
        right.pack(side='left', fill='both', expand=True)
        tb = tk.Frame(right, bg=CARD)
        tb.pack(fill='x', padx=8, pady=(6, 4))
        tk.Label(tb, text='ACTIONS', bg=CARD, fg=TXT, font=FONT_B).pack(side='left')
        self.count = tk.Label(tb, text='0 actions', bg=CARD, fg=MUTED, font=FONT)
        self.count.pack(side='left', padx=8)
        for text, cmd in (('Clear', self.clear), ('Save', self.save), ('Load', self.load), ('Delete', self.delete_sel), ('↓', lambda: self.move_action(1)), ('↑', lambda: self.move_action(-1)), ('+ Wait', self.insert_wait)):
            mkbtn(tb, text, cmd, padx=7, pady=2).pack(side='right', padx=(0, 3))
        tk.Label(right, text='  #    TYPE    DELAY BEFORE      ACTION', bg=CARD2, fg=MUTED, font=('Consolas', 8), anchor='w', pady=3).pack(fill='x', padx=8)
        tk.Label(right, text='Double-click to change a delay. + Wait adds a pause after the selected action.', bg=CARD, fg=MUTED, font=SMALL, anchor='w').pack(side='bottom', fill='x', padx=8, pady=(2, 5))
        frame = tk.Frame(right, bg=CARD)
        frame.pack(fill='both', expand=True, padx=8)
        self.lb = tk.Listbox(frame, bg=CARD, fg=TXT, font=('Consolas', 9), bd=0, highlightthickness=0, activestyle='none', selectbackground='#304c6b', selectforeground='white', selectmode='extended', exportselection=False)
        sb = tk.Scrollbar(frame, command=self.lb.yview, relief='flat', bd=0)
        sb.pack(side='right', fill='y')
        self.lb.config(yscrollcommand=sb.set)
        self.lb.pack(fill='both', expand=True)
        self.lb.bind('<Double-Button-1>', self.edit_delay)
        self.refresh_labels()

    def spin(self, parent, var, lo, hi, inc, width, cmd=None, bg=CARD2):
        s = tk.Spinbox(parent, from_=lo, to=hi, increment=inc, width=width, textvariable=var, bg=bg, fg=TXT, bd=0, relief='flat', buttonbackground=HOVER, insertbackground=TXT, highlightthickness=0, font=FONT, command=cmd)
        if cmd:
            s.bind('<KeyRelease>', lambda e: cmd())
            s.bind('<FocusOut>', lambda e: cmd())
        return s

    def show_home(self):
        self.editor.pack_forget()
        self.home.pack(fill='both', expand=True)

    def show_editor(self):
        self.home.pack_forget()
        self.editor.pack(fill='both', expand=True)

    def open_macro(self, m):
        self.cur = m
        self.loading = True
        self.rep_v.set(str(m['repeat']))
        self.spd_v.set(str(m['speed']))
        self.inf_v.set(m['loop'])
        self.loading = False
        self.title_lbl.config(text=m['name'])
        self.bind_lbl.config(text=f"Shortcut: {pretty_combo(m['bind'])}")
        self.render()
        self.idle_status()
        self.show_editor()

    def go_home(self):
        if self.recording:
            self.toggle_rec()
        self.save_macros()
        idx = self.macros.index(self.cur) if self.cur in self.macros else None
        self.cur = None
        self.refresh_home(idx)
        self.show_home()

    def sync_macro_opts(self):
        if self.loading or not self.cur:
            return
        try:
            rep = int(self.rep_v.get())
            if 1 <= rep <= 9999:
                self.cur['repeat'] = rep
        except ValueError:
            pass
        try:
            spd = float(self.spd_v.get())
            if math.isfinite(spd) and 0.1 <= spd <= 10:
                self.cur['speed'] = spd
        except ValueError:
            pass
        self.cur['loop'] = bool(self.inf_v.get())

    def bind_current(self):
        if self.cur:
            m = self.cur
            self.ask_bind(f"Bind for '{m['name']}'", lambda combo: self.set_macro_bind(m, combo), owner=m['bind'])

    def clear_current_bind(self):
        if self.cur:
            self.set_macro_bind(self.cur, '')

    def main_options(self):
        self.opt['record_move'] = self.move_v.get()
        self.opt['sounds'] = self.sound_v.get()
        for key in ('record_move', 'sounds'):
            if key in self.v:
                self.v[key].set(self.opt[key])
        self.save_cfg()

    def refresh_labels(self):
        self.btn_rec.config(text=f"● Record [{self.hk('rec')}]")
        self.btn_play.config(text=f"▶ Play [{self.hk('play')}]")
        self.btn_stop.config(text=f"■ Stop [{self.hk('stop')}]")
        self.btn_toggle.config(text=f"{('Disable' if self.enabled else 'Enable')} hotkeys [{self.hk('toggle')}]")
        if hasattr(self, 'mlist'):
            self.home_toggle.config(text=f"{('Disable' if self.enabled else 'Enable')} hotkeys [{self.hk('toggle')}]")
            self.home_stop.config(text=f"■ Stop [{self.hk('stop')}]")

    def set_status(self, text, color):
        self.status.config(text=text, fg=color)
        self.home_status.config(text=text, fg=color)

    def idle_status(self):
        if self.enabled:
            self.set_status('● Ready', GREEN_H)
        else:
            self.set_status('● Hotkeys off', ORANGE)
        self.count.config(text=f'{len(self.actions)} actions')

    def render(self):
        self.lb.delete(0, 'end')
        for i, a in enumerate(self.actions):
            kind, text = describe_action(a, i)
            self.lb.insert('end', text)
            self.lb.itemconfig(i, fg=TYPE_COLOR[kind])
        self.count.config(text=f'{len(self.actions)} actions')

    def edit_delay(self, e):
        if self.playing or self.recording or (not self.actions):
            return
        i = self.lb.nearest(e.y)
        if not 0 <= i < len(self.actions):
            return
        value = simpledialog.askfloat('Edit timing', 'Wait before this action (ms). 1,000 ms = 1 second:', initialvalue=round(self.actions[i]['d'] * 1000, 4), minvalue=0, maxvalue=3600000, parent=self.root)
        if value is not None and math.isfinite(value):
            self.actions[i]['d'] = value / 1000
            self.render()
            self.save_macros()
            self.lb.selection_set(i)

    def insert_wait(self):
        if self.recording or self.playing or (not self.cur):
            return
        value = simpledialog.askfloat('Insert wait', 'Pause length (ms). 1,000 ms = 1 second:', initialvalue=1000, minvalue=0, maxvalue=3600000, parent=self.root)
        if value is None or not math.isfinite(value):
            return
        sel = self.lb.curselection()
        index = sel[-1] + 1 if sel else len(self.actions)
        self.actions.insert(index, {'t': 'wait', 'd': value / 1000})
        self.render()
        self.save_macros()
        self.lb.selection_set(index)
        self.lb.see(index)

    def move_action(self, direction):
        if self.recording or self.playing:
            return
        sel = self.lb.curselection()
        if len(sel) != 1:
            return
        i = sel[0]
        j = i + direction
        if 0 <= j < len(self.actions):
            self.actions[i], self.actions[j] = (self.actions[j], self.actions[i])
            self.render()
            self.save_macros()
            self.lb.selection_set(j)
            self.lb.see(j)

    def delete_sel(self):
        if self.playing or self.recording:
            return
        for i in reversed(self.lb.curselection()):
            del self.actions[i]
        self.render()
        self.save_macros()

    def clear(self):
        if self.playing or self.recording or (not self.cur):
            return
        self.actions.clear()
        self.render()
        self.save_macros()

    def save(self):
        if self.recording or self.playing or (not self.cur):
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('Chicken macro', '*.json')])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.actions, f, indent=1)
            except OSError as e:
                messagebox.showerror('Save failed', str(e), parent=self.root)

    def load(self):
        if self.playing or self.recording or (not self.cur):
            return
        path = filedialog.askopenfilename(filetypes=[('Chicken macro', '*.json')])
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                data = validate_actions(json.load(f))
            self.cur['actions'] = data
            self.render()
            self.save_macros()
        except Exception as e:
            messagebox.showerror('Load failed', str(e), parent=self.root)

    def all_binds(self):
        binds = {v: LABELS[k] for k, v in self.hot.items()}
        for m in self.macros:
            if m['bind']:
                binds[m['bind']] = m['name']
        return binds

    def ask_bind(self, title, callback, owner=None):
        if self.recording or self.playing or self.capturing:
            return
        parent = self.sw if self.sw is not None else self.root
        w = tk.Toplevel(parent)
        w.title('Set shortcut')
        w.configure(bg=BG)
        w.geometry('400x230+420+200')
        w.resizable(False, False)
        w.transient(parent)
        w.attributes('-topmost', True)
        self.apply_icon(w)
        tk.Label(w, text=title, bg=BG, fg=TXT, font=FONT_B).pack(pady=(14, 4))
        self.cap_label = tk.Label(w, text='Press your shortcut', bg=CARD, fg=GREEN_H, font=('Segoe UI', 14, 'bold'), width=22, pady=8)
        self.cap_label.pack(pady=6)
        tk.Label(w, text='Hold Ctrl, Alt or Shift, then press another key.\nOr press a single key, such as F8. Esc cancels.', bg=BG, fg=MUTED, font=FONT, justify='center').pack()
        self.cap_win, self.cap_cb, self.cap_owner = (w, callback, owner)
        self.capturing = True
        w.protocol('WM_DELETE_WINDOW', self.end_capture)

    def end_capture(self):
        self.capturing = False
        if self.cap_win is not None:
            try:
                self.cap_win.destroy()
            except tk.TclError:
                pass
        self.cap_win = self.cap_cb = None

    def finish_capture(self, combo):
        cb = self.cap_cb
        if combo == 'esc':
            self.end_capture()
            return
        used = self.all_binds()
        if combo in used and combo != self.cap_owner:
            if self.cap_label is not None:
                self.cap_label.config(text=f'{pretty_combo(combo)} is used', fg=ORANGE)
            messagebox.showwarning('Shortcut already used', f'{pretty_combo(combo)} is already used by {used[combo]}.', parent=self.cap_win)
            return
        self.end_capture()
        if cb:
            self.confirm_modifier_bind(combo, cb)

    def open_settings(self):
        if self.sw is not None:
            try:
                if self.sw.winfo_exists():
                    self.sw.lift()
                    return
            except tk.TclError:
                pass
        w = tk.Toplevel(self.root)
        w.title('Chicken settings')
        self.apply_icon(w)
        w.geometry('620x470+400+60')
        w.configure(bg=BG)
        w.attributes('-topmost', True)
        w.resizable(False, False)
        w.protocol('WM_DELETE_WINDOW', self.close_settings)
        self.sw = w
        self.v = {}
        tabbar = tk.Frame(w, bg=BG)
        tabbar.pack(fill='x', padx=10, pady=(10, 0))
        body = tk.Frame(w, bg=CARD)
        body.pack(fill='both', expand=True, padx=10, pady=8)
        frames, btns = ({}, {})

        def show(name):
            for n, f in frames.items():
                f.pack_forget()
                btns[n].config(bg=CARD2, fg=MUTED)
            frames[name].pack(fill='both', expand=True)
            btns[name].config(bg=CARD, fg=TXT)
        for name in ('Hotkeys', 'Playback', 'Recording', 'Interface', 'Startup', 'Files', 'Updates'):
            frames[name] = tk.Frame(body, bg=CARD)
            btns[name] = tk.Button(tabbar, text=name, command=lambda n=name: show(n), bg=CARD2, fg=MUTED, relief='flat', bd=0, font=FONT, cursor='hand2', padx=12, pady=5)
            btns[name].pack(side='left', padx=(0, 2))
        f = frames['Hotkeys']
        tk.Label(f, text='Click a shortcut, then press your keys.\nExample: hold Ctrl and press X, or press F8.', bg=CARD, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=12, pady=8)
        self.hk_btns = {}
        for name in ('rec', 'play', 'stop', 'toggle'):
            row = tk.Frame(f, bg=CARD)
            row.pack(fill='x', padx=12, pady=3)
            tk.Label(row, text=LABELS[name], bg=CARD, fg=TXT, width=14, anchor='w', font=FONT).pack(side='left')
            b = mkbtn(row, self.hk(name), lambda n=name: self.bind_global(n), width=16, pady=3)
            b.pack(side='left')
            self.hk_btns[name] = b
        mkbtn(f, 'Reset to default', self.reset_hot, pady=3, padx=10).pack(anchor='w', padx=12, pady=10)
        f = frames['Playback']
        self.check(f, 'precise_timing', 'More accurate timing (uses more CPU)')
        self.number(f, 'loop_delay_ms', 'Wait between repeats (ms)', 0, 60000, 10)
        self.number(f, 'start_delay_s', 'Wait before playback (ms)', 0, 60000, 100)
        f = frames['Recording']
        self.check(f, 'trim_first_delay', 'Start with the first recorded action')
        self.check(f, 'record_move', 'Record mouse movement')
        self.number(f, 'move_interval_ms', 'Time between mouse samples (ms)', 5, 1000, 5)
        f = frames['Interface']
        self.check(f, 'always_on_top', 'Keep Chicken above other windows')
        tk.Label(f, text='Chicken stays visible when you switch to another app.', bg=CARD, fg=MUTED, font=FONT).pack(anchor='w', padx=36)
        self.check(f, 'sounds', 'Play status sounds')
        self.check(f, 'skip_ctrl_warning', "Don't show the Ctrl warning")
        tk.Label(f, text='Drag the window edges to resize it. Chicken remembers your layout.', bg=CARD, fg=MUTED, font=FONT).pack(anchor='w', padx=12)
        mkbtn(f, 'Restore compact size', lambda: self.restore_geometry(reset=True), pady=3, padx=10).pack(anchor='w', padx=12, pady=6)
        txt = 'Running as administrator: YES' if self.admin else 'Running as administrator: NO\nApps running as admin may ignore Chicken.'
        tk.Label(f, text=txt, bg=CARD, fg=GREEN_H if self.admin else ORANGE, font=FONT, justify='left').pack(anchor='w', padx=12, pady=6)
        if not self.admin:
            mkbtn(f, 'Restart as administrator', self.relaunch_admin, pady=3, padx=10).pack(anchor='w', padx=12)
        f = frames['Startup']
        tk.Label(f, text='Administrator access is optional.', bg=CARD, fg=TXT, font=FONT_B).pack(anchor='w', padx=12, pady=(12, 6))
        tk.Label(f, text='Use it if the app you control also runs as administrator.\nMost apps work with normal access.', bg=CARD, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=12)
        self.check(f, 'admin_on_start', 'Request administrator access when Chicken opens')
        self.check(f, 'hide_admin_prompt', "Don't show the startup question")
        tk.Label(f, text='Windows may still ask for approval each time.\nChanges take effect the next time Chicken opens.', bg=CARD, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=12, pady=8)
        f = frames['Files']
        tk.Label(f, text='Your macro library', bg=CARD, fg=TXT, font=FONT_B).pack(anchor='w', padx=12, pady=(12, 4))
        self._files_location = tk.Label(f, text=self.opt.get('macro_folder', 'Unavailable'), bg=CARD, fg=MUTED, font=FONT, wraplength=500, justify='left')
        self._files_location.pack(anchor='w', padx=12)
        mkbtn(f, 'Open macros folder', self.open_macros_folder, padx=10, pady=4).pack(anchor='w', padx=12, pady=(8, 4))
        mkbtn(f, 'Change macro location', self.choose_macros_folder, padx=10, pady=4).pack(anchor='w', padx=12, pady=4)
        tk.Label(f, text='One file per macro. Use Save in the editor to export an action list.\nKeep library.json: it lists the files Chicken uses.', bg=CARD, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=12, pady=8)
        mkbtn(f, 'Delete saved data...', self.delete_saved_data, bg=RED, hover=RED_H, padx=10, pady=4).pack(anchor='w', padx=12, pady=4)
        mkbtn(f, 'Uninstall Chicken...', self.uninstall_chicken, padx=10, pady=4).pack(anchor='w', padx=12, pady=4)
        tk.Label(f, text='Data deletion is permanent and requires confirmation.\nUninstall is available in the installed version.', bg=CARD, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=12, pady=8)
        f = frames['Updates']
        tk.Label(f, text='Chicken ' + chicken_updates.APP_VERSION, bg=CARD, fg=TXT, font=FONT_B).pack(anchor='w', padx=12, pady=(12, 6))
        self.check(f, 'check_updates_on_start', 'Check for updates when Chicken opens')
        tk.Label(f, text='Checks the official GitHub release page. No macro data is sent.\nUpdates are never installed automatically.', bg=CARD, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=12, pady=8)
        mkbtn(f, 'Check for updates', self.check_updates, padx=12, pady=5).pack(anchor='w', padx=12, pady=6)
        show('Hotkeys')

    def bind_global(self, name):
        self.ask_bind(f'Bind for {LABELS[name]}', lambda combo: self.set_global(name, combo), owner=self.hot[name])

    def set_global(self, name, combo):
        self.hot[name] = combo
        self.save_cfg()
        self.refresh_labels()
        self.refresh_hk_btns()

    def reset_hot(self):
        taken = {m['bind'] for m in self.macros if m['bind']}
        clash = [pretty_combo(v) for v in DEFAULT_HOT.values() if v in taken]
        if clash:
            messagebox.showwarning('Cannot reset', 'A macro already uses: ' + ', '.join(clash), parent=self.sw)
            return
        self.hot = dict(DEFAULT_HOT)
        self.save_cfg()
        self.refresh_labels()
        self.refresh_hk_btns()

    def refresh_hk_btns(self):
        for n, b in self.hk_btns.items():
            try:
                b.config(text=self.hk(n))
            except tk.TclError:
                pass

    def check(self, parent, key, text):
        var = tk.BooleanVar(value=self.opt[key])
        self.v[key] = var
        tk.Checkbutton(parent, text=text, variable=var, command=self.apply_opts, bg=CARD, fg=TXT, selectcolor=CARD2, activebackground=CARD, activeforeground=TXT, bd=0, highlightthickness=0, font=FONT, anchor='w').pack(fill='x', padx=12, pady=6)

    def number(self, parent, key, text, lo, hi, inc):
        shown = round(self.opt[key] * 1000) if key == 'start_delay_s' else self.opt[key]
        var = tk.StringVar(value=str(shown))
        self.v[key] = var
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill='x', padx=12, pady=6)
        tk.Label(row, text=text, bg=CARD, fg=TXT, font=FONT).pack(side='left')
        self.spin(row, var, lo, hi, inc, 7, cmd=self.apply_opts, bg=CARD2).pack(side='right')

    def apply_opts(self):
        for key, var in self.v.items():
            try:
                value = var.get()
                if key in INT_KEYS or key in FLOAT_KEYS:
                    value = float(value)
                    if not math.isfinite(value) or value < 0:
                        continue
                    if key == 'start_delay_s':
                        value = min(60000, value) / 1000
                    elif key == 'loop_delay_ms':
                        value = int(min(60000, value))
                    else:
                        value = int(min(1000, max(5, value)))
                self.opt[key] = value
            except (ValueError, OverflowError, tk.TclError):
                pass
        self.move_v.set(self.opt['record_move'])
        self.sound_v.set(self.opt['sounds'])
        self.root.attributes('-topmost', self.opt['always_on_top'])
        self.save_cfg()

    def close_settings(self):
        if self.capturing:
            self.end_capture()
        if self.sw is not None:
            self.sw.destroy()
            self.sw = None

    def update_rects(self):
        rects = {}
        for k, w in (('main', self.root), ('set', self.sw), ('cap', self.cap_win)):
            try:
                if w is not None and w.winfo_exists():
                    x, y = (w.winfo_rootx(), w.winfo_rooty())
                    rects[k] = (x, y, x + w.winfo_width(), y + w.winfo_height())
            except tk.TclError:
                pass
        self.rects = rects

    def inside(self, x, y):
        return any((a <= x <= c and b <= y <= d for a, b, c, d in list(self.rects.values())))

    def add(self, a, ts=None):
        with self.record_lock:
            if not self.recording or self.cur is None:
                return
            now = ts if ts is not None else time.perf_counter()
            first = not self.cur['actions']
            a['d'] = 0.0 if first and self.opt['trim_first_delay'] else max(0.0, round(now - self.last_t, 4))
            self.last_t = max(now, self.last_t)
            self.cur['actions'].append(a)
            self.q.put(('add', None))

    def flush_pending(self):
        with self.record_lock:
            items, self.pending = (self.pending, [])
            for a, ts in items:
                self.add(a, ts)

    def swallow(self):
        return

    def on_click(self, x, y, button, pressed, injected=False):
        if self.recording and (not injected) and (not self.inside(x, y)):
            with self.record_lock:
                self.flush_pending()
                self.add({'t': 'click', 'x': x, 'y': y, 'b': button.name, 'p': pressed})

    def on_scroll(self, x, y, dx, dy, injected=False):
        if self.recording and (not injected) and (not self.inside(x, y)):
            with self.record_lock:
                self.flush_pending()
                self.add({'t': 'scroll', 'x': x, 'y': y, 'dx': dx, 'dy': dy})

    def on_move(self, x, y, injected=False):
        if self.recording and (not injected) and self.opt['record_move'] and (not self.inside(x, y)):
            now = time.perf_counter()
            if now - self.last_move > self.opt['move_interval_ms'] / 1000:
                self.last_move = now
                with self.record_lock:
                    self.flush_pending()
                    self.add({'t': 'move', 'x': x, 'y': y})

    def key_data(self, key, pressed):
        if isinstance(key, keyboard.Key):
            return {'t': 'key', 'k': key.name, 'p': pressed}
        vk = getattr(key, 'vk', None)
        data = {'t': 'key', 'p': pressed}
        if vk is not None:
            data['vk'] = vk
        ch = getattr(key, 'char', None)
        if ch and ch.isprintable():
            data['c'] = ch
        return data

    def lookup(self, combo):
        for name, v in self.hot.items():
            if v == combo:
                return ('g', name)
        for m in self.macros:
            if m['bind'] and m['bind'] == combo:
                return ('m', m['id'])
        return None

    def on_press(self, key, injected=False):
        if injected:
            return
        kn = key_name(key)
        if kn in self.down:
            if kn in self.suppressed:
                self.swallow()
            return
        self.down.add(kn)
        mod = mod_name(key)
        if mod:
            self.mods.add(mod)
            if self.capturing:
                self.q.put(('cap_live', make_combo(self.mods, '...')))
            elif self.recording:
                with self.record_lock:
                    if self.recording:
                        self.pending.append((self.key_data(key, True), time.perf_counter()))
            return
        combo = make_combo(self.mods, kn)
        if self.capturing:
            self.suppressed.add(kn)
            self.q.put(('capture', combo))
            self.swallow()
            return
        target = self.lookup(combo)
        if target:
            self.suppressed.add(kn)
            if target == ('g', 'toggle') or self.enabled:
                with self.record_lock:
                    self.pending.clear()
                self.q.put(('hot', target))
                self.swallow()
            return
        if self.recording:
            with self.record_lock:
                self.flush_pending()
                self.add(self.key_data(key, True))

    def on_release(self, key, injected=False):
        if injected:
            return
        kn = key_name(key)
        self.down.discard(kn)
        mod = mod_name(key)
        if mod:
            self.mods.discard(mod)
            if kn in self.ignore_up:
                self.ignore_up.discard(kn)
                return
            if self.recording:
                with self.record_lock:
                    self.flush_pending()
                    self.add(self.key_data(key, False))
            return
        if kn in self.suppressed:
            self.suppressed.discard(kn)
            self.swallow()
            return
        if self.recording and (not self.capturing):
            self.add(self.key_data(key, False))

    def toggle_system(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        self.refresh_labels()
        if not (self.recording or self.playing):
            self.idle_status()
        self.sound('hotkeys_on' if self.enabled else 'hotkeys_off')

    def toggle_rec(self):
        if self.playing or self.cur is None:
            return
        if not self.recording:
            with self.record_lock:
                self.cur['actions'].clear()
                self.render()
                self.last_t = time.perf_counter()
                self.last_move = 0.0
                self.pending = []
                self.ignore_up = {n for n in list(self.down) if n in MOD_ALIASES}
                self.recording = True
            self.set_status('● RECORDING', RED_H)
            self.sound('record')
        else:
            with self.record_lock:
                self.recording = False
                self.pending = []
                self.cur['actions'] = finalize_actions(self.cur['actions'], self.opt['trim_first_delay'])
            self.render()
            self.save_macros()
            self.idle_status()
            self.sound('stop')

    def play_current(self):
        if self.cur:
            self.play(self.cur)

    def play(self, macro):
        if self.recording or self.playing or (not macro['actions']):
            return
        try:
            validate_actions(macro['actions'])
        except ValueError as e:
            messagebox.showerror('Cannot play', str(e), parent=self.root)
            return
        self.playing = True
        self.playing_id = macro['id']
        self.stop_flag = False
        self.stop_sound_sent = False
        self.set_status(f"▶ Playing {macro['name'][:18]}", BLUE)
        self.sound('play')
        reps = 0 if macro['loop'] else macro['repeat']
        actions = json.loads(json.dumps(macro['actions']))
        threading.Thread(target=self.run, args=(actions, reps, macro['speed']), daemon=True).start()

    def stop(self):
        self.stop_flag = True
        if self.recording:
            self.toggle_rec()
        elif self.playing and (not self.stop_sound_sent):
            self.stop_sound_sent = True
            self.sound('stop')

    def wait(self, secs):
        end = time.perf_counter() + secs
        precise = self.opt['precise_timing']
        while True:
            if self.stop_flag:
                return False
            left = end - time.perf_counter()
            if left <= 0:
                return True
            if precise:
                if left > 0.003:
                    time.sleep(0.001)
            else:
                time.sleep(min(left, 0.01))

    def to_key(self, a):
        if 'k' in a:
            return keyboard.Key[a['k']]
        if a.get('vk') is not None:
            return keyboard.KeyCode.from_vk(a['vk'])
        return a['c']

    def run(self, actions, reps, speed):
        held_keys, held_btns = (set(), set())
        try:
            until = time.perf_counter() + 3
            while self.mods and time.perf_counter() < until:
                if not self.wait(0.01):
                    return
            if not self.wait(self.opt['start_delay_s']):
                return
            n = 0
            while reps == 0 or n < reps:
                for i, a in enumerate(actions):
                    if not self.wait(a['d'] / speed):
                        return
                    self.q.put(('hl', i))
                    t = a['t']
                    if t in ('move', 'click', 'scroll'):
                        self.mctl.position = (a['x'], a['y'])
                    if t == 'click':
                        b = mouse.Button[a['b']]
                        if a['p']:
                            self.mctl.press(b)
                            held_btns.add(b)
                        else:
                            self.mctl.release(b)
                            held_btns.discard(b)
                    elif t == 'scroll':
                        self.mctl.scroll(a['dx'], a['dy'])
                    elif t == 'key':
                        k = self.to_key(a)
                        if a['p']:
                            self.kctl.press(k)
                            held_keys.add(k)
                        else:
                            self.kctl.release(k)
                            held_keys.discard(k)
                n += 1
                if not self.wait(self.opt['loop_delay_ms'] / 1000):
                    return
        except Exception:
            self.q.put(('error', traceback.format_exc()))
        finally:
            for k in held_keys:
                try:
                    self.kctl.release(k)
                except Exception:
                    pass
            for b in held_btns:
                try:
                    self.mctl.release(b)
                except Exception:
                    pass
            self.q.put(('done', None))

    def handle_hot(self, target):
        kind, ident = target
        if kind == 'g':
            if ident == 'rec':
                if self.cur is not None:
                    self.toggle_rec()
            elif ident == 'play':
                if self.cur is not None:
                    self.play(self.cur)
            elif ident == 'stop':
                self.stop()
            else:
                self.toggle_system()
            return
        macro = next((m for m in self.macros if m['id'] == ident), None)
        if macro is None or self.recording:
            return
        if self.playing:
            if self.playing_id == ident:
                self.stop()
            return
        self.play(macro)

    def poll(self):
        self.update_rects()
        try:
            while True:
                cmd, data = self.q.get_nowait()
                if cmd == 'add':
                    if self.cur is not None:
                        i = len(self.actions) - 1
                        if i >= 0:
                            kind, text = describe_action(self.actions[i], i)
                            self.lb.insert('end', text)
                            self.lb.itemconfig('end', fg=TYPE_COLOR[kind])
                            self.lb.see('end')
                            self.count.config(text=f'{len(self.actions)} actions')
                elif cmd == 'hl':
                    if self.cur is not None and self.cur['id'] == self.playing_id and (data < self.lb.size()):
                        self.lb.selection_clear(0, 'end')
                        self.lb.selection_set(data)
                        self.lb.see(data)
                elif cmd == 'error':
                    messagebox.showerror('Playback stopped', data, parent=self.root)
                elif cmd == 'done':
                    if not self.stop_sound_sent:
                        self.sound('stop')
                    self.playing = False
                    self.playing_id = None
                    self.idle_status()
                elif cmd == 'cap_live':
                    if self.capturing and self.cap_label is not None:
                        self.cap_label.config(text=pretty_combo(data).replace('...', '…'), fg=TXT)
                elif cmd == 'capture':
                    if self.capturing:
                        self.finish_capture(data)
                elif cmd == 'hot':
                    self.handle_hot(data)
                elif cmd == 'update_result':
                    self.show_update_result(*data)
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def close_app(self):
        self.stop_flag = True
        with self.record_lock:
            self.recording = False
        if self.playing:
            self.root.after(25, self.close_app)
            return
        if self.root.state() == 'normal':
            self.opt['geometry'] = self.root.geometry()
        self.save_cfg()
        self.save_macros()
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
        self.root.destroy()

    def windows_key_filter(self, msg, data):
        if msg not in (256, 257, 260, 261):
            return True
        if data.flags & 16:
            return True
        if not hasattr(self, '_native_held'):
            self._native_held = set()
            self._native_blocked = set()
        vk = int(data.vkCode)
        pressed = msg in (256, 260)
        repeated = pressed and vk in self._native_held
        if pressed:
            self._native_held.add(vk)
        else:
            self._native_held.discard(vk)
        mods = set()
        for codes, name in (((17, 162, 163), 'ctrl'), ((18, 164, 165), 'alt'), ((16, 160, 161), 'shift'), ((91, 92), 'cmd')):
            if any((v in self._native_held for v in codes)):
                mods.add(name)
        if vk in (16, 17, 18, 160, 161, 162, 163, 164, 165, 91, 92):
            return True
        if not pressed:
            if vk in self._native_blocked:
                self._native_blocked.discard(vk)
                self.keyboard_listener.suppress_event()
            return True
        if vk in self._native_blocked:
            self.keyboard_listener.suppress_event()
        if 65 <= vk <= 90 or 48 <= vk <= 57:
            name = chr(vk).lower()
        elif 96 <= vk <= 105:
            name = 'num' + str(vk - 96)
        else:
            name = None
            for k in keyboard.Key:
                if getattr(k.value, 'vk', None) == vk:
                    name = k.name
                    break
            if name is None:
                name = key_name(keyboard.KeyCode.from_vk(vk))
        combo = make_combo(mods, name)
        target = self.lookup(combo)
        capturing = bool(self.capturing)
        active = target is not None and (self.enabled or target == ('g', 'toggle'))
        if not capturing and (not active):
            return True
        self._native_blocked.add(vk)
        if not repeated:
            if capturing:
                self.q.put(('capture', combo))
            else:
                with self.record_lock:
                    self.pending.clear()
                    recorded = set()
                    if self.cur is not None:
                        for a in self.cur['actions']:
                            if a.get('t') == 'key' and 'k' in a:
                                if a.get('p'):
                                    recorded.add(a['k'])
                                else:
                                    recorded.discard(a['k'])
                    for modkey in list(self.down):
                        if modkey in MOD_ALIASES and modkey not in recorded:
                            self.ignore_up.add(modkey)
                self.q.put(('hot', target))
        self.keyboard_listener.suppress_event()
        return True

    def center_dialog(self, window, parent):
        window.update_idletasks()
        left, top = (0, 0)
        right, bottom = (window.winfo_screenwidth(), window.winfo_screenheight())
        try:
            import ctypes as c
            from ctypes import wintypes as wt

            class MonitorInfo(c.Structure):
                _fields_ = [('cbSize', wt.DWORD), ('rcMonitor', wt.RECT), ('rcWork', wt.RECT), ('dwFlags', wt.DWORD)]
            u = c.windll.user32
            monitor_from = u.MonitorFromWindow
            monitor_from.argtypes = [wt.HWND, wt.DWORD]
            monitor_from.restype = wt.HANDLE
            get_info = u.GetMonitorInfoW
            get_info.argtypes = [wt.HANDLE, c.POINTER(MonitorInfo)]
            get_info.restype = wt.BOOL
            info = MonitorInfo()
            info.cbSize = c.sizeof(info)
            if get_info(monitor_from(parent.winfo_id(), 2), c.byref(info)):
                r = info.rcWork
                left, top, right, bottom = (r.left, r.top, r.right, r.bottom)
        except (AttributeError, OSError, ValueError):
            pass
        width, height = (window.winfo_reqwidth(), window.winfo_reqheight())
        x = left + max(0, (right - left - width) // 2)
        y = top + max(0, (bottom - top - height) // 2)
        window.geometry(f'{width}x{height}+{x}+{y}')

    def confirm_modifier_bind(self, combo, accepted):
        if 'ctrl' not in combo.split('+') or self.opt.get('skip_ctrl_warning', False):
            accepted(combo)
            return
        import time as clock
        import math
        parent = self.sw if self.sw is not None else self.root
        w = tk.Toplevel(parent)
        w.withdraw()
        w.title('Check your shortcut')
        w.configure(bg=BG)
        w.transient(parent)
        w.attributes('-topmost', True)
        w.resizable(False, False)
        self.apply_icon(w)
        tk.Label(w, text='Ctrl can change what your macro does', bg=BG, fg=ORANGE, font=('Segoe UI', 12, 'bold'), wraplength=440, justify='left').pack(anchor='w', padx=20, pady=(18, 10))
        tk.Label(w, text='Your shortcut: ' + pretty_combo(combo), bg=BG, fg=TXT, font=FONT_B).pack(anchor='w', padx=20, pady=(0, 10))
        for heading, text in [('What can happen', 'While a macro runs, holding Ctrl can turn its letters into shortcuts.'), ('Example', 'Your macro is typing A. You hold Ctrl to stop it. If the next A plays before you finish the Stop shortcut, the other app may receive Ctrl + A (Select all) instead of A.'), ('Safer Stop shortcut', 'Use a single key, such as F10, to stop playback without holding Ctrl.')]:
            tk.Label(w, text=heading, bg=BG, fg=TXT, font=FONT_B).pack(anchor='w', padx=20, pady=(5, 2))
            tk.Label(w, text=text, bg=BG, fg=TXT, font=FONT, justify='left', wraplength=440).pack(anchor='w', padx=20, pady=(0, 7))
        tk.Label(w, text='Chicken does not yet prevent this. Ctrl alone does not replay A.', bg=BG, fg=MUTED, font=FONT, wraplength=440, justify='left').pack(anchor='w', padx=20, pady=(2, 6))
        remember = tk.BooleanVar(value=False)
        tk.Checkbutton(w, text="Don't show this Ctrl warning again", variable=remember, bg=BG, fg=TXT, selectcolor=CARD2, activebackground=BG, activeforeground=TXT, font=FONT, bd=0, highlightthickness=0).pack(anchor='w', padx=16, pady=(7, 2))
        row = tk.Frame(w, bg=BG)
        row.pack(fill='x', padx=20, pady=(8, 18))
        state = {'after': None, 'closed': False}
        deadline = clock.monotonic() + 5

        def close():
            if state['closed']:
                return
            state['closed'] = True
            if state['after'] is not None:
                try:
                    w.after_cancel(state['after'])
                except tk.TclError:
                    pass
            w.destroy()

        def keep():
            if state['closed'] or clock.monotonic() < deadline:
                return
            if remember.get():
                self.opt['skip_ctrl_warning'] = True
                self.save_cfg()
            close()
            accepted(combo)

        def choose_another():
            close()
            self.ask_bind('Choose a different shortcut', accepted)
        cancel = mkbtn(row, 'Choose another shortcut', choose_another, padx=12, pady=7)
        cancel.pack(side='left')
        button = mkbtn(row, 'Use this shortcut (5s)', keep, bg=GREEN, hover=GREEN_H, padx=12, pady=7)
        button.pack(side='right', padx=(12, 0))
        button.config(state='disabled', disabledforeground=MUTED)

        def tick():
            if state['closed']:
                return
            left = max(0, math.ceil(deadline - clock.monotonic()))
            if not left:
                state['after'] = None
                button.config(text='Use this shortcut', state='normal')
            else:
                button.config(text=f'Use this shortcut ({left}s)')
                state['after'] = w.after(100, tick)
        w.protocol('WM_DELETE_WINDOW', close)
        w.bind('<Escape>', lambda e: close())
        w.update_idletasks()
        self.center_dialog(w, parent)
        w.deiconify()
        w.lift()
        w.grab_set()
        cancel.focus_set()
        deadline = clock.monotonic() + 5
        tick()

    def startup_admin(self):
        if self.admin or '--chicken-elevation-attempted' in sys.argv:
            return
        if self.opt['admin_on_start']:
            self.relaunch_admin()
        elif not self.opt['hide_admin_prompt']:
            self.admin_prompt()

    def admin_prompt(self):
        w = tk.Toplevel(self.root)
        w.withdraw()
        w.title('Administrator access')
        w.configure(bg=BG)
        w.transient(self.root)
        w.resizable(False, False)
        w.attributes('-topmost', True)
        self.apply_icon(w)
        tk.Label(w, text='Run Chicken as administrator?', bg=BG, fg=TXT, font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=20, pady=(18, 10))
        tk.Label(w, text='Most apps work with normal access.\n\nAdministrator access may help when the app you want to control\nalso runs as administrator. Only use it when needed.\n\nWindows will ask you to approve the request.', bg=BG, fg=TXT, font=FONT, justify='left', wraplength=450).pack(anchor='w', padx=20)
        always = tk.BooleanVar(value=self.opt['admin_on_start'])
        hide = tk.BooleanVar(value=self.opt['hide_admin_prompt'])
        for text, var in [('Request administrator access whenever Chicken opens', always), ("Don't show this question again", hide)]:
            tk.Checkbutton(w, text=text, variable=var, bg=BG, fg=TXT, selectcolor=CARD2, activebackground=BG, activeforeground=TXT, font=FONT, bd=0, highlightthickness=0).pack(anchor='w', padx=16, pady=(10, 0))
        tk.Label(w, text='These options do not hide the Windows security prompt.\nYou can change them in Settings > Startup.', bg=BG, fg=MUTED, font=FONT, justify='left').pack(anchor='w', padx=20, pady=(8, 0))
        row = tk.Frame(w, bg=BG)
        row.pack(fill='x', padx=20, pady=18)

        def choose(elevate):
            self.opt['admin_on_start'] = always.get()
            self.opt['hide_admin_prompt'] = hide.get()
            self.save_cfg()
            w.destroy()
            if elevate:
                self.relaunch_admin()
        mkbtn(row, 'Continue normally', lambda: choose(False), padx=12, pady=7).pack(side='left')
        mkbtn(row, 'Restart as administrator', lambda: choose(True), bg=GREEN, hover=GREEN_H, padx=12, pady=7).pack(side='right', padx=(12, 0))
        w.protocol('WM_DELETE_WINDOW', lambda: choose(False))
        w.bind('<Escape>', lambda e: choose(False))
        w.update_idletasks()
        self.center_dialog(w, self.root)
        w.deiconify()
        w.lift()
        w.grab_set()

    def relaunch_admin(self):
        if self.admin:
            return
        if self.recording or self.playing:
            messagebox.showinfo('Stop your macro first', 'Stop recording or playback before restarting Chicken.', parent=self.sw or self.root)
            return
        self.save_cfg()
        self.save_macros()
        try:
            args = [a for a in sys.argv[1:] if a != '--chicken-elevation-attempted']
            args.append('--chicken-elevation-attempted')
            if not getattr(sys, 'frozen', False):
                args.insert(0, os.path.abspath(sys.argv[0]))
            launch = ctypes.windll.shell32.ShellExecuteW
            launch.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
            launch.restype = ctypes.c_void_p
            result = launch(None, 'runas', sys.executable, subprocess.list2cmdline(args), RESOURCE, 1)
            if result and result > 32:
                self.close_app()
                return
        except Exception:
            pass
        messagebox.showinfo('Continuing normally', 'Administrator access was not approved or could not be started.\nChicken is still running with normal access.', parent=self.sw or self.root)

    def load_macros(self):
        self._library_ready = False
        self.library = None
        try:
            folder = self.opt.get('macro_folder', '')
            if not folder:
                folder = str(chicken_storage.documents_folder() / 'Chicken Macro' / 'Macros')
            self.library = chicken_storage.Library(folder)
            data = self.library.load()
            if data is not None:
                self.macros = [clean_macro(m) for m in data]
            else:
                if os.path.exists(MACROS):
                    with open(MACROS, encoding='utf-8') as f:
                        legacy = json.load(f)
                    self.macros = [clean_macro(m) for m in legacy['macros']]
                elif os.path.exists(LAST):
                    with open(LAST, encoding='utf-8') as f:
                        actions = validate_actions(json.load(f))
                    self.macros = [new_macro('Macro 1', actions)] if actions else []
                else:
                    self.macros = []
                self.library.save(self.macros)
                check = self.library.load()
                if check != self.macros:
                    raise ValueError('The copied macro library could not be verified.')
            self.opt['macro_folder'] = str(self.library.folder)
            self._library_ready = True
            self.save_cfg()
        except Exception as e:
            self.macros = []
            messagebox.showerror('Macro storage unavailable', 'Your old files have not been deleted. Changes will not be saved until storage is available.\n\n' + str(e), parent=self.root)

    def save_macros(self):
        if not getattr(self, '_allow_saves', True) or not getattr(self, '_library_ready', False):
            return
        try:
            self.library.save(self.macros)
        except Exception as e:
            messagebox.showerror('Could not save macros', str(e), parent=self.root)

    def open_macros_folder(self):
        if not getattr(self, '_library_ready', False):
            messagebox.showerror('Folder unavailable', 'Restart Chicken after making Documents available.', parent=self.sw or self.root)
            return
        try:
            os.startfile(str(self.library.folder))
        except OSError as e:
            messagebox.showerror('Could not open folder', str(e), parent=self.sw or self.root)

    def choose_macros_folder(self):
        if self.busy() or not getattr(self, '_library_ready', False):
            return
        parent = self.sw or self.root
        base = filedialog.askdirectory(title='Choose a location for Chicken Macro', parent=parent)
        if not base:
            return
        from pathlib import Path
        target = Path(base) / 'Chicken Macro' / 'Macros'
        if target.resolve() == self.library.folder.resolve():
            return
        if target.exists() and any(target.iterdir()):
            messagebox.showerror('Choose another location', 'The target Macros folder already contains files. Choose a different location.', parent=parent)
            return
        if not messagebox.askokcancel('Copy macro library', 'Copy your macros to:\n' + str(target) + '\n\nThe old folder will remain as a backup. Use the new folder from now on?', parent=parent):
            return
        old_folder = self.opt['macro_folder']
        try:
            candidate = chicken_storage.Library(target)
            candidate.save(self.macros)
            if candidate.load() != self.macros:
                raise ValueError('Copy verification failed.')
            self.opt['macro_folder'] = str(target)
            self.write_json(CFG, {**self.opt, 'hotkeys': self.hot}, indent=1)
            self.library = candidate
            self._files_location.config(text=str(target))
            messagebox.showinfo('Folder changed', 'Your macros were copied. The old folder was kept as a backup.', parent=parent)
        except Exception as e:
            self.opt['macro_folder'] = old_folder
            messagebox.showerror('Folder not changed', str(e), parent=parent)

    def delete_saved_data(self):
        self._cleanup_result = 10
        if self.busy() or not getattr(self, '_library_ready', False):
            return
        parent = self.sw or self.root
        text = 'Permanently delete all Chicken data in these locations?\n\nMacro library: ' + str(self.library.folder) + '\nSettings and original migration files: ' + HERE + '\n\nThis removes saved macros, shortcuts, preferences, and the original legacy macro files.\nChicken will close. Reinstalling cannot restore this data.\n\nExported copies, previous custom library folders, development backups, and the app itself are NOT removed.\nOther files in these folders will be left alone.'
        if not messagebox.askyesno('Delete all saved data?', text, parent=parent, icon='warning', default='no'):
            return
        answer = simpledialog.askstring('Confirm permanent deletion', 'Type delete to permanently remove Chicken data (any capitalization):', parent=parent)
        if answer is None:
            return
        if answer.strip().casefold() != 'delete':
            messagebox.showinfo('Saved data kept', 'The confirmation did not match. Your saved data will not be deleted.', parent=parent)
            return
        from pathlib import Path
        try:
            targets = self.library.deletion_targets()
            for path in (CFG, MACROS, LAST, CFG + '.tmp', MACROS + '.tmp', LAST + '.tmp'):
                p = Path(path)
                if p.is_symlink():
                    raise ValueError('A linked data file cannot be safely deleted: ' + str(p))
                if p.exists():
                    if not p.is_file() or p.resolve().parent != Path(HERE).resolve():
                        raise ValueError('Unsafe data path: ' + str(p))
                    targets.append(p)
        except Exception as e:
            messagebox.showerror('Nothing deleted', str(e), parent=parent)
            return
        self._allow_saves = False
        errors = []
        for p in targets:
            try:
                if p.exists():
                    p.unlink()
            except OSError as e:
                errors.append(str(e))
        for folder in (self.library.folder, self.library.folder.parent, Path(HERE)):
            try:
                folder.rmdir()
            except OSError:
                pass
        if errors:
            messagebox.showerror('Some files could not be deleted', '\n'.join(errors) + '\n\nChicken will close without saving.', parent=parent)
        else:
            messagebox.showinfo('Saved data deleted', 'Chicken will now close. The application has not been uninstalled.', parent=parent)
        self._cleanup_result = 20 if errors else 0
        self.close_app()

    def uninstall_chicken(self):
        if self.busy():
            return
        if not getattr(sys, 'frozen', False):
            messagebox.showinfo('Source version', 'This is the Python source version, not an installed app.\nA Windows uninstaller will be available after we build the installer.\n\nUse Delete saved data to remove macros and settings. Delete your development folder manually only if you no longer need it.', parent=self.sw or self.root)
            return
        uninstaller = os.path.join(os.path.dirname(sys.executable), 'unins000.exe')
        if not os.path.isfile(uninstaller):
            messagebox.showinfo('Portable version', 'No installer uninstaller was found. Delete saved data here if needed, then close Chicken and remove its portable executable manually.', parent=self.sw or self.root)
            return
        try:
            self.save_cfg()
            self.save_macros()
            subprocess.Popen([uninstaller], cwd=os.path.dirname(uninstaller))
            self.close_app()
        except OSError as e:
            messagebox.showerror('Could not open uninstaller', str(e), parent=self.sw or self.root)

    def startup_update_check(self):
        if self.opt.get('check_updates_on_start', False):
            self.check_updates(manual=False)

    def check_updates(self, manual=True):
        if getattr(self, '_update_check_busy', False):
            if manual:
                messagebox.showinfo('Checking for updates', 'An update check is already in progress.', parent=self.sw or self.root)
            return
        self._update_check_busy = True

        def worker():
            try:
                info = chicken_updates.check_release()
            except Exception:
                info = {'status': 'error', 'message': 'The update check could not be completed.'}
            self.q.put(('update_result', (info, manual)))
        threading.Thread(target=worker, daemon=True).start()

    def show_update_result(self, info, manual):
        if self.recording or self.playing or self.capturing or (self.root.grab_current() is not None):
            self.root.after(1000, lambda: self.show_update_result(info, manual))
            return
        self._update_check_busy = False
        parent = self.sw or self.root
        status = info.get('status')
        if status == 'new':
            if messagebox.askyesno('Update available', 'Chicken ' + info['version'] + ' is available.\nYou are using ' + chicken_updates.APP_VERSION + '.\n\nOpen the official GitHub release page?\nNothing will be downloaded or installed automatically.', parent=parent):
                import webbrowser
                webbrowser.open(chicken_updates.RELEASE_PAGE)
        elif manual and status == 'current':
            messagebox.showinfo('Up to date', 'Chicken ' + chicken_updates.APP_VERSION + ' is up to date.', parent=parent)
        elif manual and status == 'none':
            messagebox.showinfo('No release available', 'No published stable release with a matching Windows installer is available yet.', parent=parent)
        elif manual:
            messagebox.showinfo('Update check unavailable', info.get('message', 'Please try again later.'), parent=parent)

def uninstall_data_confirmation():
    """Run before installer removes app files; never invoke App startup or autosave."""
    root = tk.Tk()
    root.withdraw()
    root.title('Chicken data removal')
    root.attributes('-topmost', True)
    try:
        from ctypes import wintypes
        find = ctypes.windll.user32.FindWindowW
        find.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        find.restype = wintypes.HWND
        if find(None, 'Chicken'):
            messagebox.showwarning('Close Chicken first', 'Chicken is still open. Saved data will NOT be deleted.\nUninstall will continue, keeping your data.', parent=root)
            return 20
        ctx = App.__new__(App)
        ctx.root = root
        ctx.sw = None
        ctx.recording = False
        ctx.playing = False
        ctx._cleanup_result = 10
        ctx.opt = dict(DEFAULTS)
        ctx.hot = dict(DEFAULT_HOT)
        ctx.load_cfg()
        folder = ctx.opt.get('macro_folder', '')
        if not folder:
            folder = str(chicken_storage.documents_folder() / 'Chicken Macro' / 'Macros')
        ctx.library = chicken_storage.Library(folder)
        ctx._library_ready = True
        ctx.close_app = lambda: None
        ctx.delete_saved_data()
        return ctx._cleanup_result
    except Exception as e:
        messagebox.showerror('Data removal stopped', 'Saved data could not be completely removed.\n\n' + str(e), parent=root)
        return 20
    finally:
        root.destroy()
if __name__ == '__main__':
    if '--uninstall-data-confirm' in sys.argv:
        raise SystemExit(uninstall_data_confirmation())
    else:
        App()
