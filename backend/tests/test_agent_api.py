from app.api import agent


def test_user_triggered_agent_routes_are_registered():
    routes = {
        route.path
        for route in agent.router.routes
        if hasattr(route, "path")
    }

    assert "/agent/run-weekly-summary" in routes
    assert "/agent/run-reminders" in routes
    assert "/cron/weekly-summary" not in routes
