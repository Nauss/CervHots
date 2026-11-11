"""Thin manual Tk launcher; no acquisition, API or audio in the panel process."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def operator_scratch(env):
    """Explicit override or dedicated user Hermes operator scratch, never OS temp."""
    value = env.get('CERVHOTS_SCRATCH')
    if value:
        result = Path(value)
    else:
        result = Path(env['LOCALAPPDATA'])/'hermes/operator-playtest/cache/scratch'
    if not result.is_absolute():
        raise ValueError('absolute scratch required')
    return result


class Controller:
    def __init__(self, root, python, scratch, *, popen=subprocess.Popen, request_stop=None):
        self.root, self.python, self.scratch = Path(root), Path(python), Path(scratch)
        self.popen = popen
        if request_stop is None:
            from .session_control import request_stop
        self.request_stop = request_stop
        self.process = self.log = self.output = self.stop_file = None
        self.stopping = False
        self.message = 'Prêt — aucun jeu, API ou son lancé.'

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def _launch(self, args, parent):
        if self.running:
            return False
        self.poll()
        try:
            if not self.python.is_file() or not self.scratch.is_absolute():
                raise ValueError('runtime unavailable')
            self.scratch.mkdir(parents=True, exist_ok=True)
            parent.mkdir(parents=True, exist_ok=False)
            self.log = (parent/'console.jsonl').open('x', encoding='utf-8')
            env = dict(os.environ, TMPDIR=str(self.scratch), TEMP=str(self.scratch), TMP=str(self.scratch))
            self.process = self.popen([str(self.python), '-B', '-m', 'cerveau.playtest', *args],
                cwd=self.root, env=env, stdout=self.log, stderr=subprocess.STDOUT)
            self.stopping = False
            self.message = 'Processus démarré ; journal : '+str(parent/'console.jsonl')
            return True
        except (OSError, ValueError):
            if self.log is not None:
                self.log.close()
                self.log = None
            self.message = 'Démarrage refusé : vérifier Python produit et droits des chemins.'
            return False

    def check(self):
        if self.running:
            return False
        self.output = self.stop_file = None
        return self._launch([], self.root/'out/playtest-ui'/('check-'+uuid.uuid4().hex))

    def start(self, identity, *, voice=False, confirm=lambda: False):
        if self.running:
            self.message = 'Ancien processus encore vivant ; attendre sa fermeture.'
            return False
        if not identity or not Path(identity).is_absolute() or not Path(identity).is_file():
            self.message = 'Choisir un fichier identité privé existant (aucune saisie de pseudo).'
            return False
        if voice and not confirm():
            self.message = 'Voix annulée ; aucun démarrage.'
            return False
        parent = self.root/'out/playtest-ui'/('run-'+uuid.uuid4().hex)
        self.output, self.stop_file = parent/'session', parent/'STOP'
        args = ['--live', '--player-file', str(identity), '--output-dir', str(self.output),
                '--stop-file', str(self.stop_file), '--collection', 'positions', '--coach-mode', 'macro',
                '--max-seconds', '1800']
        if voice:
            args.append('--mumble')
        return self._launch(args, parent)

    def stop(self):
        if not self.running:
            self.poll()
            return
        self.stopping = True
        if self.output is None:
            self.message = 'Préflight en cours ; attendre son retour, aucun lecteur lancé.'
            return
        result = self.request_stop(self.output, self.stop_file)
        if result['state'] in ('published', 'already_present'):
            self.message = 'STOP publié ; attendre la fermeture du processus (appel en cours borné).'
            self.stopping = False
        else:
            self.message = 'STOP en attente du contrôle enregistré ; pas de nouveau démarrage.'

    def poll(self):
        if self.process is None:
            return
        code = self.process.poll()
        if code is None:
            if self.stopping:
                self.stop()
            return
        if self.log is not None:
            self.log.close()
            self.log = None
        self.process = None
        self.stopping = False
        self.message = f'Processus terminé (code {code}). Consulter le journal/summary avant une nouvelle session.'


def build_panel(window, controller):
    """Tk imported only by explicit UI launch; widget construction has zero IO."""
    import tkinter as tk
    from tkinter import filedialog, messagebox
    window.title('CervHots — test manuel')
    identity = tk.StringVar()
    status = tk.StringVar(value=controller.message)
    tk.Label(window, text='Volskaya / build 98348 — macro limitée outnumbered — 30 min maximum\n'
        'Positions alliées tentées ; pas de coach spatial.\n'
        'Mumble : serveur à démarrer MANUELLEMENT ; aucun serveur/bot lancé ici.').pack(padx=20, pady=12)
    def choose():
        path = filedialog.askopenfilename(title='Fichier identité privée existant', parent=window)
        if path:
            identity.set(path)
    tk.Button(window, text='Choisir fichier identité privée', command=choose).pack()
    tk.Label(window, textvariable=identity, wraplength=600).pack()
    def action(callback):
        callback()
        status.set(controller.message)
    buttons = []
    for label, callback in (
        ('Vérifier (sans mémoire/API/son)', controller.check),
        ('Démarrer silencieux', lambda: controller.start(identity.get())),
        ('Démarrer voix Mumble', lambda: controller.start(identity.get(), voice=True,
            confirm=lambda: messagebox.askyesno('Activation manuelle voix',
                'Autoriser lecture native, API, Piper et diffusion Mumble ?\n'
                'Le serveur Mumble doit déjà être démarré manuellement.', parent=window)))):
        button = tk.Button(window, text=label, command=lambda fn=callback: action(fn))
        button.pack(fill='x', padx=20, pady=3)
        buttons.append(button)
    tk.Button(window, text='Arrêter', command=lambda: action(controller.stop)).pack(pady=5)
    tk.Label(window, textvariable=status, wraplength=600).pack(padx=20, pady=12)
    closing = False
    def close():
        nonlocal closing
        if controller.running:
            closing = True
            action(controller.stop)
        else:
            window.destroy()
    def tick():
        controller.poll()
        status.set(controller.message)
        for button in buttons:
            button.configure(state='disabled' if controller.running else 'normal')
        if closing and not controller.running:
            window.destroy()
            return
        window.after(200, tick)
    window.protocol('WM_DELETE_WINDOW', close)
    window.after(200, tick)
    return status


def main():
    import tkinter as tk
    python = Path(os.environ.get('CERVHOTS_PYTHON', str(ROOT/'tts/.venv/Scripts/python.exe')))
    window = tk.Tk()
    build_panel(window, Controller(ROOT, python, operator_scratch(os.environ)))
    window.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
