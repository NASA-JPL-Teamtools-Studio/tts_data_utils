#Standard Library Imports
import re
import traceback
from functools import wraps

#Installed Library Imports
# None yet

#Teamtool Studio Imports
from tts_utilities.logger import create_logger

log = create_logger(__name__)

GLOBAL_ENABLE_INVULNERABLE = True

def set_global_invulnerable():
    """
    Globally enables the 'invulnerable' error-handling logic.
    """
    global GLOBAL_ENABLE_INVULNERABLE
    GLOBAL_ENABLE_INVULNERABLE = True
    
def clear_global_invulnerable():
    """
    Globally disables the 'invulnerable' logic, allowing exceptions to raise normally.
    """
    global GLOBAL_ENABLE_INVULNERABLE
    GLOBAL_ENABLE_INVULNERABLE = False

def filter_on_attr_regex(all_data, **kwargs):
    """
    Filters a list of objects based on attribute values matching regex patterns.

    **The Concept:**
    Instead of writing multiple loops to find objects with specific properties, 
    this utility allows you to pass keyword arguments where the key is the 
    attribute name and the value is a regex pattern.

    **How it works:**
    It dynamically compiles each provided pattern into a strict start-to-finish 
    regex (using `^` and `$`). It then iterates through the dataset and returns 
    only those objects where *every* specified attribute satisfies its 
    corresponding regex match.

    :param all_data: A list of objects to be filtered.
    :type all_data: list
    :param kwargs: Attribute names and their corresponding regex strings.
    :type kwargs: str
    :return: A list of filtered objects.
    :rtype: list
    """
    regex_dict = {_k: re.compile(f'^{_v}$') for _k, _v in kwargs.items() if _v is not None}
    return [_ for _ in all_data if all([_v.match(getattr(_, _k)) for _k, _v in regex_dict.items()])]

def log_exception(user_message):
    """Simple shorthand for logging an exception the screen with a clarifying message"""
    exc = traceback.format_exc()
    log.error(user_message + '\n' + exc)

def invulnerable(func):
    """
    Decorator function to make a function/method 'invulnerable' to exceptions, instead logging errors.

    **The Concept:**
    In automated data pipelines, a single malformed record shouldn't necessarily 
    kill a long-running process. This decorator acts as a "safety net" or "containment 
    field" around a function.

    **How it works:**
    If an exception occurs within the decorated function:
    1. It checks the `GLOBAL_ENABLE_INVULNERABLE` flag.
    2. If enabled, it captures the function/class name.
    3. It logs a descriptive error and the full stack trace.
    4. It returns `None` rather than crashing, allowing the rest of the program to continue.

    :param func: The function or method to be protected.
    :type func: callable
    """
    def wrapper_invulnerable(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        
        except Exception as e:
            if not GLOBAL_ENABLE_INVULNERABLE:
                raise e
            # This grabs the function name and calling class name from the input 'self' argument
            # This implementation assumes the decorated function is a class method, which is OK for this application
            if len(args) > 0 and hasattr(args[0],'__class__') and hasattr(args[0].__class__,'__name__'):
                fname = "{}.{}".format(args[0].__class__.__name__,func.__name__)
            else:
                fname = func.__name__

            # Print the offending function in the log
            log_exception(f'Contained Exception during function {fname}')
                
            # Print the full stack trace
            return None
    
    return wrapper_invulnerable

def exec_invulnerable(func, *args, **kwargs):
    """
    Executes a function immediately within an 'invulnerable' wrapper.

    **The Concept:**
    Similar to the `@invulnerable` decorator, but used for one-off executions 
    where you want to try-catch a call inline without decorating the original 
    definition.

    :param func: The function to execute.
    :type func: callable
    :param args: Positional arguments for the function.
    :param kwargs: Keyword arguments for the function.
    :return: The function result or None if an exception was caught.
    """
    @invulnerable
    @wraps(func)
    def wrapper():
        return func(*args, **kwargs)
    return wrapper()

NO_CACHE = object()

class cached_property:
    """
    A property decorator that caches its result after the first access.

    **The Concept:**
    Some properties are expensive to calculate (e.g., parsing a large file or 
    performing a complex diff). `cached_property` ensures that the logic runs 
    exactly once; subsequent calls simply return the stored value.

    **How it works:**
    The first time the property is accessed, it executes the underlying function 
    and saves the result to a private attribute (prefixed with `_`). On future 
    calls, it checks for this attribute and returns it directly, bypassing 
    the calculation logic.
    """
    def __init__(self, func):
        self.func = func        
        self.attr_name = None
    
    def __set_name__(self, _, name):
        if self.attr_name is not None:
            raise Exception('Cannot assign cached property twice')
        self.attr_name = f'_{name}'
    
    def __get__(self, obj, objtype=None):
        if not hasattr(obj, self.attr_name):
            setattr(obj, self.attr_name, self.func(obj))
        return getattr(obj, self.attr_name)