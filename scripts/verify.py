import pathlib, re, subprocess, sys, os
root=pathlib.Path(__file__).parents[1]; compose=(root/'deploy/local/compose.yaml').read_text()
generated={'.git','build','dist','demo','out','__pycache__','.ad3-evolution','.test-state'}
alltext='\n'.join(p.read_text(errors='ignore') for p in root.rglob('*') if p.is_file() and not generated.intersection(p.parts) and p.name != 'verify.py' and p.suffix.lower() not in {'.exe','.zip','.pyc','.sqlite3'})
assert ':latest' not in compose and '0.0.0.0:' not in compose and 'external: true' not in compose
for bad in ('.'+'claude','model: '+'sonnet','s'+'k-', 'PRIVATE'+' KEY'): assert bad not in alltext
env={**os.environ,'PYTHONPATH':str(root/'src')}
raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests'],cwd=root,env=env))
