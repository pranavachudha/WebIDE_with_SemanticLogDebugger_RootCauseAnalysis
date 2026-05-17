import re


def _suggest_fix(exception_type: str, message: str, similar_bugs: list) -> str:
    if exception_type == "ModuleNotFoundError":
        missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", message)
        package = missing.group(1) if missing else "the missing package"
        return f"Install or add `{package}` to the active environment, then verify the interpreter used by the IDE matches that environment."
    if exception_type == "ImportError":
        return "Check the imported symbol/module name, dependency version, circular imports, and whether the package is installed in this interpreter."
    if exception_type == "AttributeError" and "NoneType" in message:
        return "Trace where the value becomes `None`; add validation, initialize a concrete object, or guard before calling the attribute."
    if exception_type == "KeyError":
        return "Use `.get()`, validate dictionary keys, or ensure upstream code populates the missing key before access."
    if exception_type == "IndexError":
        return "Check sequence length before indexing and review loop boundaries."
    if exception_type == "NameError":
        return "Define the name before use and check for typos or missing imports."
    if exception_type == "TypeError":
        return "Inspect the value types at the failing call and convert or branch before the operation."
    if similar_bugs:
        return similar_bugs[0].get("metadata", {}).get("fixed_code", "")[:500]
    return "Inspect the failing frame and compare the runtime value with the expected contract."


def analyze_error(exception_type: str, message: str, traceback_str: str, similar_bugs: list) -> dict:
    """
    Synthesizes a root cause analysis based on the error and retrieved similar bugs.
    """
    
    # Base analysis based on standard exception types
    base_analysis = ""
    if exception_type == "ModuleNotFoundError":
        base_analysis = f"The active Python environment cannot resolve a required module. {message}"
    elif exception_type == "ImportError":
        base_analysis = f"The import machinery found a module but could not import the requested name or dependency. {message}"
    elif exception_type == "AttributeError":
        if "NoneType" in message:
            base_analysis = "A variable was initialized as None or unexpectedly returned None before an attribute was accessed. This indicates a null reference propagation issue."
        else:
            base_analysis = f"An attempt was made to access a non-existent attribute. ({message})"
    elif exception_type == "TypeError":
        base_analysis = f"An operation or function was applied to an object of inappropriate type. ({message})"
    elif exception_type == "IndexError":
        base_analysis = f"An attempt was made to access a list or sequence index that is out of range. ({message})"
    elif exception_type == "KeyError":
        base_analysis = f"A dictionary key was not found. ({message})"
    elif exception_type == "NameError":
        base_analysis = f"A local or global name is not found, indicating an undefined variable. ({message})"
    else:
        base_analysis = f"An unexpected {exception_type} occurred: {message}."
        
    # Enrich with similar bugs from BugsInPy
    if similar_bugs and len(similar_bugs) > 0:
        best_match = similar_bugs[0]
        score = best_match.get("score", 0)
        
        # Only include if it's somewhat similar
        if score > 0.3:
            metadata = best_match.get("metadata", {})
            historical_rca = metadata.get("rca_summary", "")
            
            enrichment = f"\n\nHistorical analysis (similarity: {score:.2f}): "
            enrichment += f"Similar BugsInPy failures point to this pattern: {historical_rca}"
            base_analysis += enrichment
            
    return {
        "summary": base_analysis,
        "suggested_fix": _suggest_fix(exception_type, message, similar_bugs),
        "confidence": round(similar_bugs[0].get("score", 0.35), 3) if similar_bugs else 0.35,
        "matched_patterns": [
            {
                "bug_id": bug.get("bug_id"),
                "project": bug.get("metadata", {}).get("project", ""),
                "score": round(bug.get("score", 0), 3),
                "root_cause": bug.get("metadata", {}).get("rca_summary", ""),
            }
            for bug in similar_bugs[:3]
        ],
    }
