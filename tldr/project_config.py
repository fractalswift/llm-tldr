"""Project configuration parser for web/serverless frameworks.

Extracts entry points from configuration files to improve dead code detection.
Supports:
- Serverless Framework (serverless.yml)
- AWS SAM (template.yaml) - future
- Next.js (package.json detection) - future
"""

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
    
    # Future: Add more parsers here
    # - parse_sam_template()
    # - parse_nextjs_config()
    # - parse_package_json()
    
    if entry_points:
        logger.info(f"Loaded {len(entry_points)} entry points from config files")
    
    return entry_points
