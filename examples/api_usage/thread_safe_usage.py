"""Thread-safe usage example for CarryMem v0.2.0+.

This example demonstrates:
1. Multiple threads can safely access the same CarryMem instance
2. ThreadLocal connections ensure no race conditions
3. Proper resource cleanup with context managers
"""

import threading
import time
from carrymem import CarryMem

def worker(worker_id: int, cm: CarryMem, num_operations: int = 10):
    """Worker thread that performs memory operations."""
    print(f"Worker {worker_id} started")

    for i in range(num_operations):
        cm.classify_and_remember(f"Worker {worker_id} completed task {i}")
        cm.recall_memories(query=f"Worker {worker_id}")
        time.sleep(0.01)

    print(f"Worker {worker_id} finished")

def main():
    print("=== CarryMem Thread-Safe Usage Example (v0.2.0+) ===\n")

    with CarryMem() as cm:
        num_threads = 5
        num_operations = 10

        print(f"Starting {num_threads} threads, each performing {num_operations} operations...\n")

        threads = []
        start_time = time.time()

        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i, cm, num_operations))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        elapsed = time.time() - start_time
        print(f"\n✓ All completed in {elapsed:.2f} seconds")

        stats = cm.get_stats()
        print(f"\nFinal statistics:")
        print(f"  Total memories: {stats['total_count']}")
        print(f"  Expected: {num_threads * num_operations}")

        for i in range(num_threads):
            results = cm.recall_memories(query=f"Worker {i}")
            print(f"  Worker {i} memories: {len(results)}")

if __name__ == "__main__":
    main()
