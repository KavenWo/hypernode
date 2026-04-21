import ast
import re

def parse_ai_error(exc: Exception) -> str:
    """Extract a clean, human-readable message and code from AI service exceptions."""
    try:
        err_str = str(exc)
        
        # Try to extract a dictionary-like payload from the error string
        dict_match = re.search(r"(\{.+\})", err_str.replace('\n', ' '))
        code = "Unknown"
        message = err_str
        
        if dict_match:
            try:
                # Use ast.literal_eval for safer evaluation of the dict-like string
                parsed = ast.literal_eval(dict_match.group(1).replace(': true', ': True').replace(': false', ': False').replace(': null', ': None'))
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict) and 'error' in parsed[0]:
                    parsed = parsed[0]
                if isinstance(parsed, dict) and 'error' in parsed:
                    err = parsed['error']
                    code = str(err.get('code', "Unknown"))
                    message = err.get('message', err_str)
            except (ValueError, SyntaxError, TypeError):
                pass
        
        if code == "Unknown":
            # Fallback to checking common exception attributes
            code_attr = getattr(exc, "code", None)
            if code_attr is not None:
                code = str(code_attr)
            message = getattr(exc, "message", getattr(exc, "details", err_str))

        # Final display logic with custom mappings
        suffix = " Fallback plan is being used."
        
        if code == "429":
            return f"AI Service Quota Exceeded (429).{suffix}"
        elif code == "503":
            return f"AI Service High Demand (503).{suffix}"
        else:
            # Truncate long messages for other errors
            clean_message = str(message).strip()
            if len(clean_message) > 120:
                clean_message = clean_message[:120] + "..."
            return f"{clean_message}{suffix}"

    except Exception as e:
        # Absolute safety fallback
        return f"AI Service Error. Fallback plan is being used."