from typer.testing import CliRunner
from athenaeum.main_cli import app

runner = CliRunner()

def test_version_flag():
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert res.stdout.strip()

def test_index_creates_output(tmp_path):
    data = tmp_path / "file.txt"
    data.write_text("hello")
    out = tmp_path / "idx"
    res = runner.invoke(
        app,
        ["index", str(tmp_path), "--include", "*.txt", "--output", str(out), "--no-recursive"],
    )
    assert res.exit_code == 0
    assert out.exists()
