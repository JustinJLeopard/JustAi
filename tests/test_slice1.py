"""Slice 1: Glass Aurora Redesign — structural tests."""

import pathlib

DASH = pathlib.Path(__file__).resolve().parents[1] / "dashboard" / "src"


class TestDesignSystem:
    def test_theme_css_exists(self):
        assert (DASH / "styles" / "theme.css").exists()

    def test_theme_css_has_dark_tokens(self):
        css = (DASH / "styles" / "theme.css").read_text()
        assert "--bg-void" in css
        assert "--rose-500" in css
        assert "--font-mono" in css

    def test_theme_css_has_light_mode(self):
        css = (DASH / "styles" / "theme.css").read_text()
        assert '[data-theme="light"]' in css

    def test_old_index_css_removed(self):
        assert not (DASH / "index.css").exists()


class TestComponents:
    def test_sidebar_exists(self):
        assert (DASH / "components" / "Sidebar.tsx").exists()

    def test_popover_exists(self):
        assert (DASH / "components" / "Popover.tsx").exists()

    def test_theme_toggle_exists(self):
        assert (DASH / "components" / "ThemeToggle.tsx").exists()

    def test_metric_card_exists(self):
        assert (DASH / "components" / "MetricCard.tsx").exists()

    def test_pipeline_exists(self):
        # The pipeline visualization lives in ControlPlaneStages.tsx (renamed
        # from the sprint-era Pipeline.tsx during the control-plane redesign).
        assert (DASH / "components" / "ControlPlaneStages.tsx").exists()


class TestViews:
    def test_agent_registry_exists(self):
        assert (DASH / "views" / "AgentRegistry.tsx").exists()

    def test_all_views_exist(self):
        views = [
            "MissionControl",
            "TaskBoard",
            "RunHistory",
            "TrajectoryViewer",
            "MemoryBrowser",
            "AgentRegistry",
        ]
        for v in views:
            assert (DASH / "views" / f"{v}.tsx").exists(), f"Missing view: {v}"


class TestHooks:
    def test_use_theme_exists(self):
        assert (DASH / "hooks" / "useTheme.ts").exists()

    def test_use_keyboard_exists(self):
        assert (DASH / "hooks" / "useKeyboard.ts").exists()


class TestAppStructure:
    def test_app_imports_sidebar(self):
        app = (DASH / "App.tsx").read_text()
        assert "Sidebar" in app

    def test_app_has_grouped_nav(self):
        app = (DASH / "App.tsx").read_text()
        assert "observability" in app
        assert "agents" in app

    def test_index_html_has_theme_attr(self):
        html = (DASH.parent / "index.html").read_text()
        assert 'data-theme="dark"' in html

    def test_index_html_has_jetbrains_mono(self):
        html = (DASH.parent / "index.html").read_text()
        assert "JetBrains+Mono" in html or "JetBrains Mono" in html
