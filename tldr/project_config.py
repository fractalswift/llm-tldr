"""Project configuration parser for web/serverless frameworks.

Extracts entry points from configuration files to improve dead code detection.
Supports:
- Serverless Framework (serverless.yml)
- TanStack Router (package.json detection)
"""

import json
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def parse_serverless_handlers(project_root: Path) -> List[str]:
    """Parse serverless.yml to extract Lambda handler function names.
    
    Args:
        project_root: Project root directory
        
    Returns:
        List of handler function names (e.g., ["create", "get", "delete"])
        
    Example serverless.yml:
        functions:
          createUser:
            handler: src/handlers/users.create  # Extracts "create"
          getUser:
            handler: handlers/users.get         # Extracts "get"
    """
    handlers = []
    
    # Check for serverless.yml or serverless.yaml
    config_paths = [
        project_root / "serverless.yml",
        project_root / "serverless.yaml",
    ]
    
    config_file = None
    for path in config_paths:
        if path.exists():
            config_file = path
            break
    
    if not config_file:
        return []
    
    try:
        import yaml
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config or not isinstance(config, dict):
            return []
        
        # Extract handlers from functions section
        functions = config.get('functions', {})
        if not isinstance(functions, dict):
            return []
        
        for func_config in functions.values():
            if not isinstance(func_config, dict):
                continue
                
            handler = func_config.get('handler', '')
            if not handler:
                continue
            
            # Handler format: "file.function" or "path/to/file.function"
            # Extract the function name (part after last dot)
            if '.' in handler:
                function_name = handler.split('.')[-1]
                handlers.append(function_name)
                logger.debug(f"Extracted handler: {function_name} from {handler}")
            else:
                # Sometimes handler is just the function name
                handlers.append(handler)
                logger.debug(f"Extracted handler: {handler}")
        
        logger.info(f"Parsed {config_file.name}: found {len(handlers)} handlers")
        return handlers
        
    except ImportError:
        logger.warning("PyYAML not installed, cannot parse serverless.yml")
        return []
    except Exception as e:
        logger.warning(f"Failed to parse {config_file}: {e}")
        return []


def parse_package_json_frameworks(project_root: Path) -> List[str]:
    """Detect frameworks from package.json and return entry point patterns.
    
    Searches for package.json files in the project (excluding node_modules)
    and detects file-based routing frameworks.
    
    Args:
        project_root: Project root directory
        
    Returns:
        List of entry point patterns (e.g., ["routes/"] for TanStack Router)
        
    Supports:
        - TanStack Router: Detects @tanstack/react-router or @tanstack/router-plugin
          Returns "routes/" to mark all route files as entry points
    """
    entry_patterns = []
    
    try:
        # Find all package.json files (excluding node_modules, .serverless, etc.)
        package_json_files = []
        for pkg_file in project_root.rglob("package.json"):
            # Skip if in excluded directories
            parts = pkg_file.parts
            if any(excl in parts for excl in ["node_modules", ".serverless", ".venv", "venv", "dist", "build"]):
                continue
            package_json_files.append(pkg_file)
        
        # Parse each package.json
        for pkg_file in package_json_files:
            try:
                with open(pkg_file, 'r', encoding='utf-8') as f:
                    pkg_data = json.load(f)
                
                if not isinstance(pkg_data, dict):
                    continue
                
                # Combine dependencies and devDependencies
                deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                
                # Check for TanStack Router
                if '@tanstack/react-router' in deps or '@tanstack/router-plugin' in deps:
                    # Add routes/ as entry point pattern
                    # This matches any file path containing "routes/"
                    if "routes/" not in entry_patterns:
                        entry_patterns.append("routes/")
                        logger.info(f"Detected TanStack Router in {pkg_file.relative_to(project_root)}, adding routes/ as entry pattern")
                
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to parse {pkg_file}: {e}")
                continue
        
        return entry_patterns
        
    except Exception as e:
        logger.warning(f"Error scanning for package.json files: {e}")
        return []


def load_project_entry_points(project_root: Path) -> List[str]:
    """Load all entry points from project configuration files.
    
    Args:
        project_root: Project root directory
        
    Returns:
        Combined list of entry point patterns from all config sources
    """
    entry_points = []
    
    # Parse Serverless Framework config
    try:
        serverless_handlers = parse_serverless_handlers(project_root)
        entry_points.extend(serverless_handlers)
    except Exception as e:
        logger.warning(f"Error loading serverless handlers: {e}")
    
    # Parse package.json for framework detection
    try:
        framework_patterns = parse_package_json_frameworks(project_root)
        entry_points.extend(framework_patterns)
    except Exception as e:
        logger.warning(f"Error loading framework patterns: {e}")
    
    if entry_points:
        logger.info(f"Loaded {len(entry_points)} entry points from config files")
    
    return entry_points
