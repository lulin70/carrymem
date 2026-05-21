#!/usr/bin/env python3
"""Local CI gate simulator — run this to check all gates before pushing."""
import os, re, sys, subprocess

PASS = 0
FAIL = 1
errors = []

def gate(name):
    def decorator(fn):
        def wrapper():
            print(f"\n{'='*60}")
            print(f"  GATE: {name}")
            print(f"{'='*60}")
            try:
                result = fn()
                if result == PASS:
                    print(f"  ✅ PASS")
                    return PASS
                else:
                    print(f"  ❌ FAIL")
                    return FAIL
            except Exception as e:
                print(f"  ❌ ERROR: {e}")
                return FAIL
        return wrapper
    return decorator


@gate("GATE 0: Required files exist")
def check_files():
    required = [
        "README.md", "CONTRIBUTING.md", "LICENSE", "CHANGELOG.md",
        "docs/README.md", "docs/i18n/README-CN.md", "docs/i18n/README-JP.md",
        ".github/workflows/ci.yml",
        "src/carrymem/__init__.py",
        "src/carrymem/utils/__init__.py",
        "src/carrymem/layers/__init__.py",
    ]
    for f in required:
        if not os.path.exists(f):
            print(f"  MISSING: {f}")
            return FAIL
        print(f"  ✓ {f}")
    return PASS


@gate("GATE 1: Lint (flake8 fatal errors)")
def check_lint():
    r = subprocess.run(
        ["python3", "-m", "flake8", "src/", "tests/",
         "--count", "--select=E9,F63,F7,F82", "--show-source"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(r.stdout[:500])
        return FAIL
    print("  No fatal lint errors")
    return PASS


@gate("GATE 2a: i18n — no Chinese in non-i18n source")
def check_i18n_chinese():
    i18n_whitelist = ['language.py', 'context.py', 'pattern_analyzer.py', 'tools.py', '__main__.py',
                     '__init__.py', 'confirmation.py',
                     'expander.py', 'merger.py']
    found = []
    for root, dirs, files in os.walk('src'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache')]
        for f in files:
            if not f.endswith('.py'):
                continue
            fp = os.path.join(root, f)
            rp = os.path.relpath(fp)
            if any(w in rp for w in i18n_whitelist):
                continue
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    for ln, line in enumerate(fh, 1):
                        s = line.strip()
                        if s.startswith("'zh-cn:") or s.startswith('"zh-cn:') or \
                           'label_zh=' in s or 'zh_name=' in s or '# i18n' in s:
                            continue
                        if re.search(r'[\u4e00-\u9fff]', line):
                            found.append(f"  {rp}:{ln}")
            except Exception:
                pass
    if found:
        print(f"  {len(found)} lines with Chinese:")
        for f in found[:10]:
            print(f)
        return FAIL
    print("  No Chinese characters outside i18n data")
    return PASS


@gate("GATE 2b: i18n — no mangled comments")
def check_mangled():
    result = subprocess.run(
        ["grep", "-r", "# Comment in Chinese removed", "src/", "--include=*.py"],
        capture_output=True, text=True
    )
    if result.stdout.strip():
        print(result.stdout[:300])
        return FAIL
    print("  No mangled comments")
    return PASS


@gate("GATE 2c: i18n — English labels in helpers.py")
def check_helpers_labels():
    with open('src/carrymem/utils/helpers.py') as f:
        content = f.read()
    chinese = re.findall(r'(MEMORY_TYPES|MEMORY_TIERS)\[.*?\]\s*=\s*["\']([^"\']*[\u4e00-\u9fff][^"\']*)["\']', content)
    if chinese:
        for c in chinese:
            print(f"  Chinese label: {c}")
        return FAIL
    print("  All labels are English")
    return PASS


@gate("GATE 3: Unit tests")
def check_tests():
    r = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "--tb=short", "-q"],
        capture_output=True, text=True, timeout=120
    )
    last_lines = r.stdout.strip().split('\n')[-5:]
    for l in last_lines:
        print(f"  {l}")
    if r.returncode != 0:
        return FAIL
    return PASS


@gate("GATE 4: Security — bare except:")
def check_bare_except():
    r = subprocess.run(
        ["grep", "-rn", "except:", "src/", "--include=*.py"],
        capture_output=True, text=True
    )
    bare = []
    for line in r.stdout.strip().split('\n'):
        if not line:
            continue
        if 'except Exception' in line or 'except (' in line:
            continue
        bare.append(line)
    if bare:
        print(f"  {len(bare)} bare except: clauses:")
        for b in bare[:5]:
            print(f"  {b}")
        return FAIL
    print("  No bare except: clauses")
    return PASS


@gate("GATE 5: Version consistency")
def check_version():
    with open('src/carrymem/__version__.py') as f:
        src_ver = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', f.read()).group(1)
    
    setup_ver = None
    with open('setup.py') as f:
        content = f.read()
        if "'version':" in content or '"version":' in content or 'version=' in content:
            m = re.search(r'version["\']?\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                setup_ver = m.group(1)
    
    print(f"  Source: {src_ver}")
    if setup_ver:
        print(f"  Setup.py: {setup_ver}")
        if setup_ver != src_ver:
            return FAIL
    
    with open('README.md') as f:
        for line in f:
            if f'v{src_ver}' in line or f'{src_ver}' in line:
                print(f"  README: contains v{src_ver}")
                break
    return PASS


@gate("GATE 6: __init__.py in all sub-packages")
def check_init_py():
    required_dirs = ['utils', 'layers', 'adapters', 'security', 'semantic']
    base = 'src/carrymem'
    for d in required_dirs:
        init_path = os.path.join(base, d, '__init__.py')
        if not os.path.exists(init_path):
            print(f"  MISSING: {init_path}")
            return FAIL
        print(f"  ✓ {d}/__init__.py exists")
    return PASS


if __name__ == '__main__':
    print("=" * 60)
    print("  CarryMem CI Quality Gates — Local Simulator")
    print("=" * 60)

    gates = [
        check_files,
        check_lint,
        check_i18n_chinese,
        check_mangled,
        check_helpers_labels,
        check_tests,
        check_bare_except,
        check_version,
        check_init_py,
    ]

    results = [g() for g in gates]
    
    print(f"\n{'='*60}")
    passed = sum(1 for r in results if r == PASS)
    total = len(results)
    print(f"  RESULTS: {passed}/{total} gates passed")
    print(f"{'='*60}")
    
    sys.exit(0 if passed == total else 1)
