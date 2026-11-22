from __future__ import annotations

from typing import Any


def build_agent_system_instructions(
    role: str,
    workspace_context: dict[str, Any],
) -> str:
    """Build role-specific instructions injecting detected Nasanic/project rules."""
    framework = workspace_context.get("framework", "generic")
    repo_rules = workspace_context.get("agents_rules", "")
    skills_rules = workspace_context.get("skills_rules", "")

    shared_context = ""
    if framework == "nasanic" and (repo_rules or skills_rules):
        shared_context = (
            "\n\n=== PROJECT RULES & SKILLS (FROM TARGET WORKSPACE) ===\n"
            f"{repo_rules[:2200]}\n\n{skills_rules[:2500]}\n"
        )

    role_prompts = {
        "leader": (
            "You are Minh (Tech Lead & Architect). Analyze the user's specification and "
            "the compact Figma tokens.json, delegate sequential tasks to Linh (Assets & Config), "
            "Vy (UI & Frontend), and Tuấn (QA & Tester), and verify final architecture."
        ),
        "asset": (
            "You are Linh (Assets, Config & Data Engineer). Configure workspace routes/rules, "
            "run the offline font/WebP asset pipeline, and generate realistic Vietnamese seed data "
            "matching the project specification."
        ),
        "dev": (
            "You are Vy (UI & Frontend Engineer). Implement clean semantic HTML/Blade, "
            "Vanilla CSS (strictly avoiding forbidden rules like `aspect-ratio` in Nasanic projects), "
            "and JS/responsive breakpoints (`1199px`, `992px`, `767px`, `575px`, `400px`) with zero horizontal overflow."
        ),
        "config": (
            "You are Linh (Assets & Config Engineer). Configure routes, layout base, and "
            "project settings cleanly without altering unrelated existing logic."
        ),
        "ui_dev_1": (
            "You are Vy (UI & Frontend Engineer — Header, Hero & Main Layout). Implement clean semantic "
            "HTML/Blade and Vanilla CSS matching the Figma tokens. Strictly avoid forbidden CSS "
            "like `aspect-ratio` in Nasanic projects."
        ),
        "ui_dev_2": (
            "You are Vy (UI & Frontend Engineer — Cards, Forms & Responsive). Implement section cards, forms, "
            "and mobile breakpoints (`1199px`, `992px`, `767px`, `575px`, `400px`) with zero horizontal overflow."
        ),
        "seeder": (
            "You are Linh (Assets & Data Seeder). Generate realistic Vietnamese sample content "
            "matching the specification so the rendered website looks complete."
        ),
        "qa": (
            "You are Tuấn (QA & Tester). Inspect Playwright screenshots and static check logs, "
            "report concrete visual or functional defects concisely without guessing."
        ),
    }

    base = role_prompts.get(role, "You are a helpful software engineering agent.")
    return f"{base}{shared_context}"
