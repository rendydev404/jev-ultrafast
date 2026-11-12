"""Offline unit tests for jev-ag CLI formatting and parser."""

from jev_ultrafast.cli import build_parser, format_observation


def test_format_observation_renders_indexed_elements_and_options():
    sample_page = {
        "url": "https://example.com/search",
        "title": "Example Search",
        "text": "Welcome to Example Search",
        "actions": [
            {"id": "e1", "kind": "fill", "label": "Destination", "role": "combobox", "value": "Zurich", "node": 10},
            {"id": "e2", "kind": "click", "label": "Destination", "role": "combobox", "value": "Zurich", "node": 10},
            {
                "id": "e3",
                "kind": "select",
                "label": "Cabin → Economy",
                "role": "combobox",
                "current_value": "Coach",
                "value": "economy",
                "node": 20,
            },
            {"id": "wait", "kind": "wait", "label": "Wait"},
        ],
    }
    output = format_observation(sample_page, elapsed_ms=42)
    assert "URL      : https://example.com/search" in output
    assert "Elements: 2" in output
    assert "[1] combobox   (TYPE_TEXT,CLICK) Destination = 'Zurich'" in output
    assert "[2] combobox   (SELECT) Cabin = 'Coach'" in output
    assert "[2:1] option Cabin -> Economy" in output or "[2:1] option Cabin" in output


def test_cli_parser_commands():
    parser = build_parser()
    args = parser.parse_args(["--headless", "open", "https://example.com"])
    assert args.headless is True
    assert args.cmd == "open"
    assert args.url == "https://example.com"

    type_args = parser.parse_args(["--user-chrome", "type", "2", "Jakarta"])
    assert type_args.user_chrome is True
    assert type_args.cmd == "type"
    assert type_args.index == "2"
    assert type_args.text == "Jakarta"
