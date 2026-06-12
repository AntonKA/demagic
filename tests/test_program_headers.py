from pathlib import Path

from demagic.parser.program_headers import parse_program_headers


def test_parses_headers(sample_source: Path):
    headers = parse_program_headers(sample_source / "ProgramHeaders.xml")
    assert len(headers) == 2

    online = headers[0]
    assert online.prog_id == "1"
    assert online.description == "Customer List"
    assert online.task_type == "O"
    assert online.public_name == "custlist"
    assert online.interactive is True

    batch = headers[1]
    assert batch.task_type == "B"
    assert batch.public_name == ""
