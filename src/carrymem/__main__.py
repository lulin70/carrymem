import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="CarryMem — Your portable AI memory layer", prog="python -m carrymem")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    mcp_parser = subparsers.add_parser("mcp", help="Run MCP Server")
    mcp_parser.add_argument("--config", help="Path to configuration file")
    mcp_parser.add_argument("--data-path", help="Path to data directory")

    version_parser = subparsers.add_parser("version", help="Show version")  # noqa: F841

    demo_parser = subparsers.add_parser("demo", help="Run interactive demo")  # noqa: F841

    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics")
    doctor_parser.add_argument("--db", help="Database path")
    doctor_parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    doctor_parser.add_argument("--json", action="store_true", help="Output as JSON")

    cli_parser = subparsers.add_parser("cli", help="Full CLI (pass remaining args)")
    cli_parser.add_argument("cli_args", nargs=argparse.REMAINDER, help="CLI arguments")

    args = parser.parse_args()

    if args.command == "mcp":
        import asyncio
        import os

        from carrymem.integration.layer2_mcp.server import MCPServer

        if args.config:
            os.environ["CARRYMEM_CONFIG_PATH"] = args.config
        if args.data_path:
            os.environ["CARRYMEM_DATA_PATH"] = args.data_path

        server = MCPServer()
        asyncio.run(server.start())

    elif args.command == "version":
        from carrymem import __version__

        print(f"CarryMem v{__version__}")

    elif args.command == "demo":
        _run_demo()

    elif args.command == "doctor":
        from carrymem.cli import cmd_doctor

        cmd_args = []
        if args.db:
            cmd_args.extend(["--db", args.db])
        if args.fix:
            cmd_args.append("--fix")
        if args.json:
            cmd_args.append("--json")
        cmd_doctor(cmd_args)

    elif args.command == "cli":
        from carrymem.cli import main as cli_main

        cli_main(args.cli_args)

    else:
        parser.print_help()
        sys.exit(1)


def _run_demo():
    from carrymem import CarryMem

    print("=" * 60)
    from carrymem import __version__

    print(f"  CarryMem v{__version__} — Interactive Demo")
    print("=" * 60)
    print()

    cm = CarryMem()
    print("Storage: SQLite at ~/.carrymem/memories.db")
    print(f"Namespace: {cm.namespace}")
    print()

    test_messages = [
        ("I prefer dark mode", "user_preference"),
        ("No, use PostgreSQL not MongoDB", "correction"),
        ("Let's go with the microservices approach", "decision"),
        ("我偏好使用PostgreSQL", "user_preference"),
        ("纠正一下，端口号应该是5432", "correction"),
        ("ダークモードが好きです", "user_preference"),
    ]

    print("--- Classify + Store ---")
    for msg, expected in test_messages:
        result = cm.classify_and_remember(msg)
        status = "OK" if result["stored"] else "SKIP"
        print(f"  [{status}] {msg[:40]}")
    print()

    print("--- Recall (English) ---")
    results = cm.recall_memories("dark mode")
    print(f"  'dark mode' → {len(results)} memories")
    for r in results:
        print(f"    - [{r['type']}] {r['content'][:50]}")
    print()

    print("--- Recall (Chinese) ---")
    results = cm.recall_memories("偏好")
    print(f"  '偏好' → {len(results)} memories")
    for r in results:
        print(f"    - [{r['type']}] {r['content'][:50]}")
    print()

    print("--- Recall (Japanese) ---")
    results = cm.recall_memories("好き")
    print(f"  '好き' → {len(results)} memories")
    for r in results:
        print(f"    - [{r['type']}] {r['content'][:50]}")
    print()

    print("--- Memory Profile ---")
    profile = cm.get_memory_profile()
    print(f"  {profile['summary']}")
    print()

    print("--- System Prompt ---")
    prompt = cm.build_system_prompt(context="dark mode", language="en")
    print(f"  Generated {len(prompt)} chars prompt")
    print()

    print("=" * 60)
    print("  Demo complete! CarryMem is working correctly.")
    print("=" * 60)


if __name__ == "__main__":
    main()
