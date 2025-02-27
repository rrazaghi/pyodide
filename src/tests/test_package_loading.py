import pytest
import shutil
from pathlib import Path


@pytest.mark.parametrize("active_server", ["main", "secondary"])
def test_load_from_url(selenium_standalone, web_server_secondary, active_server):
    selenium = selenium_standalone
    if selenium.browser == "node":
        pytest.xfail("Loading urls in node seems to time out right now")
    if active_server == "secondary":
        url, port, log_main = web_server_secondary
        log_backup = selenium.server_log
    elif active_server == "main":
        _, _, log_backup = web_server_secondary
        log_main = selenium.server_log
        url = selenium.server_hostname
        port = selenium.server_port
    else:
        raise AssertionError()

    with log_backup.open("r") as fh_backup, log_main.open("r") as fh_main:

        # skip existing log lines
        fh_main.seek(0, 2)
        fh_backup.seek(0, 2)

        selenium.load_package(f"http://{url}:{port}/pyparsing.js")
        assert "Skipping unknown package" not in selenium.logs

        # check that all resources were loaded from the active server
        txt = fh_main.read()
        assert '"GET /pyparsing.js HTTP/1.1" 200' in txt
        assert '"GET /pyparsing.data HTTP/1.1" 200' in txt

        # no additional resources were loaded from the other server
        assert len(fh_backup.read()) == 0

    selenium.run(
        """
        from pyparsing import Word, alphas
        repr(Word(alphas).parseString('hello'))
        """
    )

    selenium.load_package(f"http://{url}:{port}/pytz.js")
    selenium.run("import pytz")


def test_load_relative_url(selenium_standalone):
    selenium_standalone.load_package("./pytz.js")
    selenium_standalone.run("import pytz")


def test_list_loaded_urls(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("pyparsing")
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == [
        "pyparsing"
    ]
    assert (
        selenium.run_js("return pyodide.loadedPackages['pyparsing']")
        == "default channel"
    )


def test_uri_mismatch(selenium_standalone):
    selenium_standalone.load_package("pyparsing")
    selenium_standalone.load_package("http://some_url/pyparsing.js")
    assert (
        "URI mismatch, attempting to load package pyparsing" in selenium_standalone.logs
    )


def test_invalid_package_name(selenium):
    with pytest.raises(
        selenium.JavascriptException,
        match=r"No known package with name 'wrong name\+\$'",
    ):
        selenium.load_package("wrong name+$")
    with pytest.raises(
        selenium.JavascriptException,
        match="No known package with name 'tcp://some_url'",
    ):
        selenium.load_package("tcp://some_url")


@pytest.mark.parametrize(
    "packages", [["pyparsing", "pytz"], ["pyparsing", "packaging"]], ids="-".join
)
def test_load_packages_multiple(selenium_standalone, packages):
    selenium = selenium_standalone
    selenium.load_package(packages)
    selenium.run(f"import {packages[0]}")
    selenium.run(f"import {packages[1]}")
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'packaging')
    assert selenium.logs.count(f"Loading {packages[0]} from") == 1
    assert selenium.logs.count(f"Loading {packages[1]} from") == 1


@pytest.mark.parametrize(
    "packages", [["pyparsing", "pytz"], ["pyparsing", "packaging"]], ids="-".join
)
def test_load_packages_sequential(selenium_standalone, packages):
    selenium = selenium_standalone
    promises = ",".join('pyodide.loadPackage("{}")'.format(x) for x in packages)
    selenium.run_js("return Promise.all([{}])".format(promises))
    selenium.run(f"import {packages[0]}")
    selenium.run(f"import {packages[1]}")
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f"Loading {packages[0]} from") == 1
    assert selenium.logs.count(f"Loading {packages[1]} from") == 1


def test_load_handle_failure(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("pytz")
    selenium.run("import pytz")
    with pytest.raises(
        selenium.JavascriptException, match="No known package with name 'pytz2'"
    ):
        selenium.load_package("pytz2")
    selenium.load_package("pyparsing")
    assert "Loading pytz" in selenium.logs
    assert "Loading pyparsing" in selenium.logs


def test_load_failure_retry(selenium_standalone):
    """Check that a package can be loaded after failing to load previously"""
    selenium = selenium_standalone
    selenium.load_package("http://invalidurl/pytz.js")
    assert selenium.logs.count("Loading pytz from") == 1
    assert selenium.logs.count("The following error occurred while loading pytz:") == 1
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == []

    selenium.load_package("pytz")
    selenium.run("import pytz")
    assert selenium.logs.count("Loading pytz from") == 2
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == ["pytz"]


def test_load_package_unknown(selenium_standalone):
    url = selenium_standalone.server_hostname
    port = selenium_standalone.server_port

    build_dir = Path(__file__).parents[2] / "build"
    shutil.copyfile(build_dir / "pyparsing.js", build_dir / "pyparsing-custom.js")
    shutil.copyfile(build_dir / "pyparsing.data", build_dir / "pyparsing-custom.data")

    try:
        selenium_standalone.load_package(f"./pyparsing-custom.js")
    finally:
        (build_dir / "pyparsing-custom.js").unlink()
        (build_dir / "pyparsing-custom.data").unlink()

    assert selenium_standalone.run_js(
        "return pyodide.loadedPackages.hasOwnProperty('pyparsing-custom')"
    )


def test_load_twice(selenium_standalone):
    selenium_standalone.load_package("pytz")
    selenium_standalone.load_package("pytz")
    assert "pytz already loaded from default channel" in selenium_standalone.logs


def test_load_twice_different_source(selenium_standalone):
    selenium_standalone.load_package(["https://foo/pytz.js", "https://bar/pytz.js"])
    assert (
        "Loading same package pytz from https://bar/pytz.js and https://foo/pytz.js"
        in selenium_standalone.logs
    )


def test_load_twice_same_source(selenium_standalone):
    selenium_standalone.load_package(["https://foo/pytz.js", "https://foo/pytz.js"])
    assert "Loading same package pytz" not in selenium_standalone.logs


def test_js_load_package_from_python(selenium_standalone):
    selenium = selenium_standalone
    to_load = ["pyparsing"]
    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            from pyodide_js import loadPackage
            await loadPackage({to_load!r})
            del loadPackage
        `);
        """
    )
    assert f"Loading {to_load[0]}" in selenium.logs
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == to_load


@pytest.mark.parametrize("jinja2", ["jinja2", "Jinja2"])
def test_load_package_mixed_case(selenium_standalone, jinja2):
    selenium = selenium_standalone
    selenium.run_js(
        f"""
        await pyodide.loadPackage("{jinja2}");
        pyodide.runPython(`
            import jinja2
        `)
        """
    )


def test_test_unvendoring(selenium_standalone):
    selenium = selenium_standalone
    selenium.run_js(
        """
        await pyodide.loadPackage("regex");
        pyodide.runPython(`
            import regex
            from pathlib import Path
            test_path =  Path(regex.__file__).parent / "test_regex.py"
            assert not test_path.exists()
        `)
        """
    )

    selenium.run_js(
        """
        await pyodide.loadPackage("regex-tests");
        pyodide.runPython(`
            assert test_path.exists()
        `)
        """
    )

    assert selenium.run_js(
        """
        return pyodide._module.packages['regex'].unvendored_tests
        """
    )


def test_install_archive(selenium):
    build_dir = Path(__file__).parents[2] / "build"
    test_dir = Path(__file__).parent
    shutil.make_archive(
        test_dir / "test_pkg", "gztar", root_dir=test_dir, base_dir="test_pkg"
    )
    build_test_pkg = build_dir / "test_pkg.tar.gz"
    if not build_test_pkg.exists():
        build_test_pkg.symlink_to((test_dir / "test_pkg.tar.gz").absolute())
    try:
        for fmt_name in ["gztar", "tar.gz", "tgz", ".tar.gz", ".tgz"]:
            selenium.run_js(
                f"""
                let resp = await fetch("test_pkg.tar.gz");
                let buf = await resp.arrayBuffer();
                pyodide.unpackArchive(buf, {fmt_name!r});
                """
            )
            selenium.run_js(
                """
                let test_pkg = pyodide.pyimport("test_pkg");
                let some_module = pyodide.pyimport("test_pkg.some_module");
                try {
                    assert(() => test_pkg.test1(5) === 26);
                    assert(() => some_module.test1(5) === 26);
                    assert(() => some_module.test2(5) === 24);
                } finally {
                    test_pkg.destroy();
                    some_module.destroy();
                    pyodide.runPython(`
                        import shutil
                        shutil.rmtree("test_pkg")
                    `)
                }
                """
            )
    finally:
        (build_dir / "test_pkg.tar.gz").unlink(missing_ok=True)
        (test_dir / "test_pkg.tar.gz").unlink(missing_ok=True)
