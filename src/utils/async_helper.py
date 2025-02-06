import asyncio
import logging
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def run_async(coro):
    """Run an async function from a synchronous context"""
    print("\n=== Starting Async Operation ===")
    loop = None
    try:
        # Try to get the running event loop
        try:
            loop = asyncio.get_running_loop()
            print("Found existing event loop")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Created new event loop")

        print(f"Executing coroutine: {coro.__name__ if hasattr(coro, '__name__') else str(coro)}")
        
        if loop.is_running():
            print("Loop is running, using run_coroutine_threadsafe")
            # Create a future in the running loop
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            result = future.result(timeout=30)  # Add timeout to prevent hanging
            print(f"Operation completed with result: {result}")
            return result
        else:
            print("Loop is not running, using run_until_complete")
            # If loop isn't running, run it until complete
            result = loop.run_until_complete(coro)
            print(f"Operation completed with result: {result}")
            return result
            
    except asyncio.TimeoutError:
        print("Async operation timed out")
        return None
    except Exception as e:
        print(f"Error in async operation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if loop and not loop.is_running():
            loop.close()
            print("Closed event loop")
        print("=== Async Operation Complete ===\n")
