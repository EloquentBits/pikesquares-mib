import subprocess
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__file__)
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logging.basicConfig(
    format="(%(module)s) %(asctime)s [%(levelname)s] %(message)s"
)

from contextlib import contextmanager

@contextmanager
def working_directory(path, cwd=Path.cwd()):
    """Changes working directory and returns to previous on exit."""
    Path(path).mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


def _cmd_exec(command, stdin='', stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    """Execute a command."""
    @dataclass
    class _CmdExecResult:
        return_code: int
        stderr: str
        stdout: str

        @property
        def success(self):
            return self.return_code == 0

        @property
        def error(self):
            return not self.success
    
    # if 'command' is a string, split the string into components
    if isinstance(command, str):
        command = command.split()
    
    logger.debug(f"executing: {' '.join(command)}")
    proc = subprocess.Popen(command, stdout=stdout, stderr=stderr, stdin=subprocess.PIPE)
    (stdout, stderr) = proc.communicate(stdin)

    if stderr:
        stderr = stderr.decode()
        logger.error(stderr)
    if stdout:
        stdout = stdout.decode()
        logger.info(stdout)
    # logger.debug("cmdexec: %s, result: %s, error: %s" % (command, stdout, stderr))

    # strip trailing whitespace, which would mess with string comparisons
    return _CmdExecResult(return_code=proc.returncode, stderr=stderr, stdout=stdout)
    # return {"return_code": proc.returncode, "stderr": stderr.rstrip(), "stdout": stdout.rstrip()}


def cmd_exec(*args, **kwargs):
    stdout = kwargs.pop('stdout', subprocess.PIPE)
    stderr = kwargs.pop('stderr', subprocess.PIPE)
    stdin = ''
    executable = kwargs.pop('executable', None)
    as_superuser = kwargs.pop('as_superuser', False)
    flag_format = kwargs.pop('flag_format', "--{flag}")
    params = []
    if as_superuser:
        params.append("sudo")
    params.append(executable)
    for arg_key, arg_value in kwargs.items():
        arg = flag_format.format(flag=arg_key).replace('_', '-')
        if isinstance(arg_value, Path):
            arg_value = str(arg_value.resolve())
        elif isinstance(arg_value, bool):
            arg_value = None
        elif isinstance(arg_value, list):
            arg = arg.rstrip("s")
            for i in arg_value:
                params.extend([arg, i])
            continue
        elif " " in arg_value:
            arg_value = f'"{arg_value}"'
        params.extend([arg, arg_value])
    params += args
    return _cmd_exec(
        command=[
            p 
            for p in params
            if p
        ],
        stdout=stdout,
        stderr=stderr,
        stdin=stdin
    )


def pkgbuild(*args, **kwargs):
    return cmd_exec(
        *args,
        **kwargs,
        executable="/usr/bin/pkgbuild",
        # stdout=subprocess.DEVNULL,
        # stderr=subprocess.DEVNULL,
    )

def installer(*args, **kwargs):
    return cmd_exec(
        *args,
        **kwargs,
        executable="/usr/sbin/installer",
        as_superuser=True,
        flag_format="-{flag}"
        # stdout=subprocess.DEVNULL,
        # stderr=subprocess.DEVNULL,
    )

def productbuild(*args, **kwargs):
    return cmd_exec(
        *args,
        **kwargs,
        executable="/usr/bin/productbuild",
        # stdout=subprocess.DEVNULL,
        # stderr=subprocess.DEVNULL,
    )


def pkgutil(*args, **kwargs):
    return cmd_exec(
        executable="/usr/bin/pkgutil",
        *args,
        **kwargs
    )


def productsign(*args, **kwargs):
    return cmd_exec(
        executable="/usr/bin/productsign",
        *args,
        **kwargs
    )
