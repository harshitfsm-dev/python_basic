import logging
import random
import time
from functools import wraps


# =============================================================================
# EXAMPLE 1: Timer Decorator
# =============================================================================
# This decorator measures how long a function takes to run.
# It works with ANY function because it uses *args and **kwargs.

def my_timer(func):
    """Prints how long the decorated function took to execute."""
    @wraps(func)  # Preserves the original function's name and docstring
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"⏱ {func.__name__} ran in {elapsed:.4f} sec")
        return result
    return wrapper


# =============================================================================
# EXAMPLE 2: Logger Decorator Factory (decorator with arguments)
# =============================================================================
# This is a DECORATOR FACTORY — a function that RETURNS a decorator.
# Why? Because we want to pass a "route" argument to customize behavior.
#
# Structure:
#   logger_decorator(route)      ← factory, takes your settings
#       └── my_logger(func)      ← the actual decorator, takes the function
#               └── wrapper()    ← runs every time the function is called

def logger_decorator(route):
    """
    Decorator factory that logs function calls with a route label.
    Generates a unique user_id for each call.

    Usage: @logger_decorator('home')
    """
    def my_logger(func):
        # Set up a dedicated logger for this function (writes to a .log file)
        logger = logging.getLogger(func.__name__)
        logger.setLevel(logging.INFO)

        # Only add handler if one doesn't already exist (avoids duplicates)
        if not logger.handlers:
            handler = logging.FileHandler(f"{func.__name__}.log")
            handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            logger.addHandler(handler)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a new user_id for EACH call (not just once)
            user_id = random.randint(1, 100_000_000_000)

            # Log the call details
            logger.info(
                f"user_id={user_id} | args={args} | kwargs={kwargs} | route={route}"
            )

            # Inject user_id as the first argument to the function
            all_args = [user_id] + list(args)
            return func(*all_args, **kwargs)

        return wrapper
    return my_logger


# --- Using both decorators together (stacked) ---
# Execution order: my_timer runs first (outer), then logger_decorator (inner)

@my_timer
@logger_decorator('home')
def test_function(user_id, age, name='Test'):
    """A sample function that simulates some work."""
    time.sleep(1)
    print(f"Hello {name}, your user id is {user_id}")


# =============================================================================
# EXAMPLE 3: Multiple Decorators — Understanding Execution Order
# =============================================================================
# When you stack decorators, they WRAP bottom-to-top but EXECUTE top-to-bottom.
#
# @decorator1        ← outermost layer (runs first and last)
# @decorator2        ← innermost layer (runs second, closer to function)
# def my_function()  ← your original code
#
# This is equivalent to: my_function = decorator1(decorator2(my_function))

def decorator1(func):
    """Outer decorator — its code runs first and finishes last."""
    @wraps(func)
    def wrapper():
        print("Decorator 1 - Before function is called.")
        func()
        print("Decorator 1 - After function is called.")
    return wrapper


def decorator2(func):
    """Inner decorator — its code runs second, right around the function."""
    @wraps(func)
    def wrapper():
        print("Decorator 2 - Before function is called.")
        func()
        print("Decorator 2 - After function is called.")
    return wrapper


@decorator1
@decorator2
def my_function():
    """The original function at the center."""
    print("Original function.")


# =============================================================================
# RUN EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("EXAMPLE 2: Timer + Logger (stacked)")
    print("=" * 60)
    test_function(27, name='Vedant')

    print()
    print("=" * 60)
    print("EXAMPLE 3: Multiple Decorators — Execution Order")
    print("=" * 60)
    my_function()
    # Output will be:
    #   Decorator 1 - Before function is called.
    #   Decorator 2 - Before function is called.
    #   Original function.
    #   Decorator 2 - After function is called.
    #   Decorator 1 - After function is called.
