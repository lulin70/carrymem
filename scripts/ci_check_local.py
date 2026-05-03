#!/usr/bin/env python3
"""Local CI check script — mirrors .github/workflows/ci.yml checks."""
import os, re, sys

def check_i18n():
    errors = []
    i18n_whitelist = [
        'language.py', 'context.py', 'pattern_analyzer.py', 'tools.py',
        '__main__.py', '__init__.py', 'confirmation.py', 'expander.py', 'merger.py',
        'failure_experience.py', 'sanitizer.py',
        'matcher.py', 'injector.py', 'templates.py',
        'conflict_detector.py', 'pattern_detector.py',
        'storage.py',
    ]
    for root, dirs, files in os.walk('src'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache')]
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
            relpath = os.path.relpath(filepath)
            if any(w in relpath for w in i18n_whitelist):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        stripped = line.strip()
                        if (stripped.startswith("'zh-cn:") or
                            stripped.startswith('"zh-cn:') or
                            stripped.startswith('# i18n') or
                            'label_zh=' in stripped or
                            'zh_name=' in stripped):
                            continue
                        if re.search(r'[\u4e00-\u9fff]', line):
                            if '"""' in line or "'''" in line:
                                continue
                            errors.append(f'{relpath}:{lineno}: {line.rstrip()[:80]}')
            except Exception as e:
                print(f'Warning: Could not read {filepath}: {e}')
    if errors:
        print(f'Found {len(errors)} lines with Chinese:')
        for err in errors[:30]:
            print(f'  {err}')
        return False
    print('No Chinese characters found in non-i18n source code.')
    return True

def check_code_quality():
    import subprocess
    result = subprocess.run(
        ['python3', '-m', 'flake8', 'src/', 'tests/',
         '--count', '--select=E9,F63,F7,F82',
         '--show-source', '--statistics'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f'Flake8 fatal errors:\n{result.stdout}{result.stderr}')
        return False
    print('No flake8 fatal errors.')
    return True

if __name__ == '__main__':
    ok = True
    print('=== i18n Check ===')
    if not check_i18n():
        ok = False
    print()
    print('=== Code Quality Check ===')
    if not check_code_quality():
        ok = False
    sys.exit(0 if ok else 1)
