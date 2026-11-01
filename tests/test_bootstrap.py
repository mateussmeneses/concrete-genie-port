import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import profiles
import run


def sfo_fixture(title="CUSA11834", version="01.00"):
    fields = {"TITLE_ID": title, "APP_VER": version}
    keys, values, entries = b"", b"", b""
    for key, value in fields.items():
        data = value.encode() + b"\0"
        entries += struct.pack("<HHIII", len(keys), 0x204, len(data), len(data), len(values))
        keys += key.encode() + b"\0"
        values += data
    return struct.pack("<4sIIII", b"\0PSF", 0x101, 20 + len(entries),
                       20 + len(entries) + len(keys), len(fields)) + entries + keys + values


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.json"
        self.args = argparse.Namespace(config=str(self.config), game_dir=None, data_dir=None)
        self.config.write_text("{}")

    def game(self, title="CUSA11834", version="01.00"):
        game = self.root / "game"
        (game / "sce_sys").mkdir(parents=True, exist_ok=True)
        (game / "sce_sys/param.sfo").write_bytes(sfo_fixture(title, version))
        (game / "eboot.bin").write_bytes(b"synthetic, not a game executable")
        return game

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CG_", "GOW3_"))}
        return subprocess.run([sys.executable, str(run.ROOT / "run.py"), *args],
                              cwd=self.root, env=env, capture_output=True, text=True, timeout=20)

    def test_help_and_config_work_without_build_or_game(self):
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--audit-runtime", result.stdout)
        result = self.cli("--config", str(self.config), "--check-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NOT VALIDATED", result.stdout)
        self.assertEqual([p.resolve() for p in self.root.iterdir()], [self.config.resolve()])

    def test_bad_config_is_rejected(self):
        for value in ('{', '[]', '{"patches":true}', '{"game_dir":3}', '{"data_dir":""}'):
            with self.subTest(value=value):
                self.config.write_text(value)
                result = self.cli("--config", str(self.config), "--check-config")
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("Traceback", result.stderr)

    def test_precedence_and_relative_paths(self):
        self.config.write_text(json.dumps({"game_dir": "game", "data_dir": "state"}))
        values = run.configuration(self.args, {})
        self.assertEqual(values["game_dir"], self.root / "game")
        self.assertEqual(values["data_dir"], self.root / "state")
        self.args.game_dir = "cli-game"
        values = run.configuration(self.args, {"CG_GAME_DIR": "env-game", "CG_DATA_DIR": "env-data"})
        self.assertEqual(values["game_dir"], self.root / "cli-game")
        self.assertEqual(values["data_dir"], self.root / "env-data")

    def test_msys_style_paths_are_translated(self):
        self.config.write_text(json.dumps({"game_dir": "/c/games/dump", "data_dir": "/d/cg-state"}))
        values = run.configuration(self.args, {})
        self.assertEqual(values["game_dir"], Path("c:/games/dump"))
        self.assertEqual(values["data_dir"], Path("d:/cg-state"))

    def test_dump_and_data_must_not_overlap(self):
        for data in ("game", "game/cache", "."):
            self.config.write_text(json.dumps({"game_dir": "game", "data_dir": data}))
            with self.assertRaisesRegex(ValueError, "overlap"):
                run.configuration(self.args, {})
        self.args.data_dir = str(run.ROOT / "references" / "state")
        with self.assertRaisesRegex(ValueError, "separate"):
            run.configuration(self.args, {})

    def test_environment_isolates_legacy_settings(self):
        env = run.runtime_environment(self.root, {"GOW3_FORCE_PATCHES": "1", "GOW3_CONFIG": "other.ini",
                                                "GOW3_UE4_SETRES_CVAR": "123", "PATH": "original"})
        self.assertNotIn("GOW3_FORCE_PATCHES", env)
        self.assertNotIn("GOW3_UE4_SETRES_CVAR", env)
        self.assertEqual(env["GOW3_CONFIG"], str(self.root / "runtime.ini"))
        self.assertEqual(env["GOW3_GPU_USER_DIR"], str(self.root / "gpu"))
        self.assertEqual(env["GOW3_USER_DIR"], str(self.root / "user"))
        self.assertEqual(env["GOW3_UPSCALER"], "none")

    def test_missing_game_is_actionable_and_does_not_create_state(self):
        result = self.cli("--data-dir", str(self.root / "state"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("No game configured", result.stderr)
        result = self.cli("--game-dir", str(self.root / "missing"), "--data-dir", str(self.root / "state"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("No eboot.bin", result.stderr)
        self.assertFalse((self.root / "state").exists())

    def test_candidate_is_never_accepted_without_a_verified_build(self):
        game = self.game()
        before = {p.relative_to(game): p.read_bytes() for p in game.rglob('*') if p.is_file()}
        result = self.cli("--game-dir", str(game), "--data-dir", str(self.root / "state"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unvalidated build: CUSA11834", result.stderr)
        self.assertIn(hashlib.sha256((game / 'eboot.bin').read_bytes()).hexdigest(), result.stderr)
        self.assertFalse((self.root / "state").exists())
        self.assertEqual(before, {p.relative_to(game): p.read_bytes() for p in game.rglob('*') if p.is_file()})
        self.assertEqual(profiles.PROFILES['CUSA11834']['builds'], {})

    def test_eu_candidate_is_recognised_but_still_unvalidated(self):
        # CUSA11875 exists in a local dump; recognising the title must not unlock the pipeline.
        game = self.game('CUSA11875', '01.07')
        digest = hashlib.sha256((game / 'eboot.bin').read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, f"Unvalidated build: CUSA11875 APP_VER=01.07") as raised:
            profiles.inspect_build(game)
        self.assertIn(digest, str(raised.exception))
        self.assertEqual(profiles.CANDIDATES['CUSA11875']['builds'], {})

    def test_unknown_title_and_malformed_sfo_are_rejected(self):
        game = self.game('CUSA99999')
        with self.assertRaisesRegex(ValueError, "Unsupported TITLE_ID"):
            profiles.inspect_build(game)
        for metadata in (b"bad", sfo_fixture("../oops"), sfo_fixture(version="bad")):
            (game / 'sce_sys/param.sfo').write_bytes(metadata)
            with self.assertRaises(ValueError):
                profiles.inspect_build(game)

    def test_exact_build_and_required_modules(self):
        game = self.game()
        digest = hashlib.sha256((game / 'eboot.bin').read_bytes()).hexdigest()
        fixture = {'CUSA11834': {'builds': {('01.00', digest): ('libc.prx',)}}}
        with patch.object(profiles, 'CANDIDATES', fixture):
            with self.assertRaisesRegex(ValueError, "Required module"):
                profiles.inspect_build(game)
            (game / 'sce_module').mkdir()
            (game / 'sce_module/libc.prx').write_bytes(b'fixture')
            self.assertEqual(profiles.inspect_build(game), ('CUSA11834', '01.00', digest, ('libc.prx',)))
            (game / 'eboot.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, "Unvalidated build"):
                profiles.inspect_build(game)

    def test_verified_fixture_routes_preparation_and_isolates_saves_from_cache(self):
        game = self.game()
        digest = hashlib.sha256((game / 'eboot.bin').read_bytes()).hexdigest()
        state = self.root / 'state'
        fixture = {'CUSA11834': {'builds': {('01.00', digest): ()}}}
        with patch.object(profiles, 'CANDIDATES', fixture), patch.object(run, 'RUNTIME', self.config), \
             patch('prepare.prepare') as prepare, patch('link_modules.link') as link, \
             patch('content_profile.prepare') as content, patch('save_backup.backup') as backup, \
             patch.object(run.subprocess, 'run', return_value=subprocess.CompletedProcess([], 17)) as child:
            result = run.main(['--config', str(self.config), '--game-dir', str(game), '--data-dir', str(state)])
        self.assertEqual(result, 17)
        out = state / 'CUSA11834' / digest / 'prepared'
        prepare.assert_called_once_with(game, out)
        link.assert_called_once_with(game, out, module_names=())
        content.assert_called_once_with(game, out)
        saves = state / 'CUSA11834' / 'user'
        backup.assert_called_once_with(saves)
        command = child.call_args.args[0]
        self.assertNotIn('--patches', command)
        self.assertEqual(command[command.index('--user') + 1], str(saves))
        self.assertEqual(child.call_args.kwargs['env']['GOW3_GPU_USER_DIR'], str(out.parent / 'gpu'))
        self.assertEqual(child.call_args.kwargs['env']['GOW3_USER_DIR'], str(saves))

    def test_child_exit_code_is_propagated(self):
        with patch.object(run, 'RUNTIME', self.config):
            with patch.object(run.subprocess, 'run', return_value=subprocess.CompletedProcess([], 23)):
                self.assertEqual(run.launch_runtime(['--audit-runtime'], self.root / 'state', {}), 23)


if __name__ == '__main__':
    unittest.main()
