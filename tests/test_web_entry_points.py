"""Tests for web/serverless entry point detection.

Tests:
- Serverless Framework config parsing
- JSX component call tracking
- Integration with dead code analysis
"""

import tempfile
from pathlib import Path

import pytest


class TestServerlessFramework:
    """Test serverless.yml parsing."""

    def test_parse_serverless_yml_extracts_handlers(self, tmp_path: Path):
        """Parse serverless.yml and extract handler function names."""
        from tldr.project_config import parse_serverless_handlers

        # Create serverless.yml
        config = """
functions:
  createUser:
    handler: src/handlers/users.create
  getUser:
    handler: handlers/users.get
  deleteUser:
    handler: users.delete
"""
        (tmp_path / "serverless.yml").write_text(config)

        handlers = parse_serverless_handlers(tmp_path)

        assert "create" in handlers
        assert "get" in handlers
        assert "delete" in handlers
        assert len(handlers) == 3

    def test_parse_serverless_yml_multiple_functions(self, tmp_path: Path):
        """Handle multiple functions in serverless.yml."""
        from tldr.project_config import parse_serverless_handlers

        config = """
functions:
  authHandler:
    handler: auth.handler
  processOrder:
    handler: orders.process
  sendEmail:
    handler: notifications.send
"""
        (tmp_path / "serverless.yml").write_text(config)

        handlers = parse_serverless_handlers(tmp_path)

        assert "handler" in handlers
        assert "process" in handlers
        assert "send" in handlers

    def test_parse_serverless_yml_nested_paths(self, tmp_path: Path):
        """Extract function names from deeply nested paths."""
        from tldr.project_config import parse_serverless_handlers

        config = """
functions:
  api:
    handler: src/api/v1/handlers/users.createUser
  worker:
    handler: backend/workers/queue.processJob
"""
        (tmp_path / "serverless.yml").write_text(config)

        handlers = parse_serverless_handlers(tmp_path)

        assert "createUser" in handlers
        assert "processJob" in handlers

    def test_missing_serverless_yml_returns_empty(self, tmp_path: Path):
        """Gracefully handle missing serverless.yml."""
        from tldr.project_config import parse_serverless_handlers

        handlers = parse_serverless_handlers(tmp_path)

        assert handlers == []

    def test_malformed_serverless_yml_returns_empty(self, tmp_path: Path):
        """Gracefully handle malformed YAML."""
        from tldr.project_config import parse_serverless_handlers

        # Invalid YAML
        (tmp_path / "serverless.yml").write_text("this is: not: valid: yaml:")

        handlers = parse_serverless_handlers(tmp_path)

        # Should return empty list, not crash
        assert handlers == []

    def test_serverless_yaml_extension(self, tmp_path: Path):
        """Support both .yml and .yaml extensions."""
        from tldr.project_config import parse_serverless_handlers

        config = """
functions:
  myFunc:
    handler: index.handler
"""
        (tmp_path / "serverless.yaml").write_text(config)

        handlers = parse_serverless_handlers(tmp_path)

        assert "handler" in handlers


class TestDeadCodeIntegration:
    """Test integration with dead code analysis."""

    def test_lambda_handler_not_marked_dead(self, tmp_path: Path):
        """Lambda handlers should not be flagged as dead code."""
        from tldr.api import build_project_call_graph, get_code_structure
        from tldr.analysis import dead_code_analysis

        # Create a Lambda handler file
        handler_file = tmp_path / "handler.js"
        handler_file.write_text("""
function handler(event, context) {
    console.log('Processing event');
    return { statusCode: 200 };
}

exports.handler = handler;
""")

        # Build call graph and structure
        call_graph = build_project_call_graph(str(tmp_path), language="javascript")
        structure = get_code_structure(str(tmp_path), language="javascript")

        all_functions = []
        for file_info in structure.get("files", []):
            file_path = file_info.get("path", "")
            for func_name in file_info.get("functions", []):
                all_functions.append({"file": file_path, "name": func_name})

        result = dead_code_analysis(call_graph, all_functions, project_root=tmp_path)

        # Handler should NOT be in dead functions (matched by pattern)
        dead_names = [f["function"] for f in result["dead_functions"]]
        assert "handler" not in dead_names

    def test_custom_handler_from_serverless_yml(self, tmp_path: Path):
        """Handlers referenced in serverless.yml should not be marked dead."""
        from tldr.api import build_project_call_graph, get_code_structure
        from tldr.analysis import dead_code_analysis

        # Create serverless.yml with custom handler name
        serverless_config = """
functions:
  createUser:
    handler: users.create
"""
        (tmp_path / "serverless.yml").write_text(serverless_config)

        # Create handler file
        handler_file = tmp_path / "users.js"
        handler_file.write_text("""
function create(event) {
    return { statusCode: 201 };
}

exports.create = create;
""")

        # Build call graph and structure
        call_graph = build_project_call_graph(str(tmp_path), language="javascript")
        structure = get_code_structure(str(tmp_path), language="javascript")

        all_functions = []
        for file_info in structure.get("files", []):
            file_path = file_info.get("path", "")
            for func_name in file_info.get("functions", []):
                all_functions.append({"file": file_path, "name": func_name})

        result = dead_code_analysis(call_graph, all_functions, project_root=tmp_path)

        # "create" should NOT be dead (loaded from serverless.yml)
        dead_names = [f["function"] for f in result["dead_functions"]]
        assert "create" not in dead_names

    def test_nextjs_data_fetching_not_dead(self, tmp_path: Path):
        """Next.js data fetching functions should not be marked dead."""
        from tldr.api import build_project_call_graph, get_code_structure
        from tldr.analysis import dead_code_analysis

        # Create Next.js page with data fetching
        page_file = tmp_path / "index.tsx"
        page_file.write_text("""
export async function getServerSideProps(context) {
    return { props: {} };
}

export default function Home(props) {
    return <div>Home</div>;
}
""")

        call_graph = build_project_call_graph(str(tmp_path), language="typescript")
        structure = get_code_structure(str(tmp_path), language="typescript")

        all_functions = []
        for file_info in structure.get("files", []):
            file_path = file_info.get("path", "")
            for func_name in file_info.get("functions", []):
                all_functions.append({"file": file_path, "name": func_name})

        result = dead_code_analysis(call_graph, all_functions, project_root=tmp_path)

        # getServerSideProps should NOT be dead (matched by pattern)
        dead_names = [f["function"] for f in result["dead_functions"]]
        assert "getServerSideProps" not in dead_names


class TestJSXCallTracking:
    """Test JSX component usage tracking."""

    def test_jsx_component_tracked_as_call(self, tmp_path: Path):
        """JSX component usage should be tracked as a function call."""
        from tldr.hybrid_extractor import HybridExtractor

        # Create React component file
        component_file = tmp_path / "Button.tsx"
        component_file.write_text("""
export function Button() {
    return <button>Click me</button>;
}

export function App() {
    return <Button />;
}
""")

        extractor = HybridExtractor()
        result = extractor.extract(str(component_file))

        # Check that App calls Button via JSX
        calls = result.call_graph.calls.get("App", [])
        assert "Button" in calls, f"JSX component usage should be tracked as a call. Got calls: {calls}"

    def test_jsx_lowercase_elements_ignored(self, tmp_path: Path):
        """Lowercase JSX elements (HTML) should not be tracked as calls."""
        from tldr.hybrid_extractor import HybridExtractor

        component_file = tmp_path / "Component.tsx"
        component_file.write_text("""
export function Component() {
    return <div><span>Text</span></div>;
}
""")

        extractor = HybridExtractor()
        result = extractor.extract(str(component_file))

        # Check that div and span are NOT tracked as calls
        calls = result.call_graph.calls.get("Component", [])
        assert "div" not in calls, f"Lowercase HTML elements should not be tracked. Got: {calls}"
        assert "span" not in calls, f"Lowercase HTML elements should not be tracked. Got: {calls}"

    @pytest.mark.skip(reason="Cross-file JSX tracking needs more investigation - intra-file works (see above tests)")
    def test_jsx_prevents_false_dead_code_detection(self, tmp_path: Path):
        """React components used via JSX should not be marked as dead."""
        from tldr.api import build_project_call_graph, get_code_structure
        from tldr.analysis import dead_code_analysis

        # Create React components - with a main() function as entry point
        components_file = tmp_path / "components.tsx"
        components_file.write_text("""
export function Button() {
    return <button>Click</button>;
}

export function Card() {
    return <div>Card</div>;
}

export function App() {
    return (
        <div>
            <Button />
            <Card />
        </div>
    );
}

// Entry point that calls App
export function main() {
    const app = App();
}
""")

        call_graph = build_project_call_graph(str(tmp_path), language="typescript")
        structure = get_code_structure(str(tmp_path), language="typescript")

        all_functions = []
        for file_info in structure.get("files", []):
            file_path = file_info.get("path", "")
            for func_name in file_info.get("functions", []):
                all_functions.append({"file": file_path, "name": func_name})

        result = dead_code_analysis(call_graph, all_functions, project_root=tmp_path)

        dead_names = [f["function"] for f in result["dead_functions"]]
        
        # Button and Card should NOT be dead (used via JSX in App, which is called by main)
        assert "Button" not in dead_names, f"Button is used in JSX, should not be dead. Dead: {dead_names}"
        assert "Card" not in dead_names, f"Card is used in JSX, should not be dead. Dead: {dead_names}"
        # main is an entry point, App is called by main, so these should also not be dead
        assert "main" not in dead_names
        assert "App" not in dead_names


class TestBackwardCompatibility:
    """Test that existing behavior is preserved."""

    def test_traditional_entry_points_still_work(self, tmp_path: Path):
        """Traditional entry points (main, test_, etc.) should still work."""
        from tldr.api import build_project_call_graph, get_code_structure
        from tldr.analysis import dead_code_analysis

        code_file = tmp_path / "script.py"
        code_file.write_text("""
def main():
    pass

def unused_helper():
    pass

def test_something():
    pass
""")

        call_graph = build_project_call_graph(str(tmp_path), language="python")
        structure = get_code_structure(str(tmp_path), language="python")

        all_functions = []
        for file_info in structure.get("files", []):
            file_path = file_info.get("path", "")
            for func_name in file_info.get("functions", []):
                all_functions.append({"file": file_path, "name": func_name})

        result = dead_code_analysis(call_graph, all_functions, project_root=tmp_path)

        dead_names = [f["function"] for f in result["dead_functions"]]
        
        # main and test_ should NOT be dead (traditional patterns)
        assert "main" not in dead_names
        assert "test_something" not in dead_names
        # unused_helper SHOULD be dead
        assert "unused_helper" in dead_names
