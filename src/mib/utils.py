import subprocess
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager
import sys

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logging.basicConfig(
    format="(%(module)s) %(asctime)s [%(levelname)s] %(message)s"
)

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
    strict_flags_after_args = kwargs.pop('strict_flags_after_args', False)
    as_superuser = kwargs.pop('as_superuser', False)
    as_superuser_gui = kwargs.pop('as_superuser_gui', False)
    superuser_gui_prompt = kwargs.pop("gui_prompt", "osascript")
    flag_format = kwargs.pop('flag_format', "--{flag}")
    params = []
    # os.system("""osascript -e 'do shell script "<commands go here>" " with administrator privileges'""")
    if as_superuser and not as_superuser_gui:
        params.append("sudo")
    params.append(executable)
    if strict_flags_after_args:
        params += args
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
    if not strict_flags_after_args:
        params += args
    if as_superuser_gui and os.getuid() != 0:
        print(f"{os.getuid()=} {os.geteuid()=}")
        shell_script = " ".join([str(p) for p in params if p])
        params = (
            '/usr/bin/osascript',
            '-e',
            f'do shell script "su -l root -c \'{shell_script}\'" with prompt "{superuser_gui_prompt}" with administrator privileges'
        )
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

@contextmanager
def superuser_cmd_context(file_name="uninstaller_tmp", gui_prompt="pikesquares sudoers change"):
    uninstaller_sudoers_path = f"/etc/sudoers.d/{file_name}"
    from getpass import getuser
    cmd_exec(
        'cat > {path} << __EOF__\n{user} ALL=(ALL) NOPASSWD: ALL\n__EOF__'.format(
            path=file_name,
            user=getuser()
        ),
        # "&&",
        # "visudo",
        # "-f", f"{uninstaller_sudoers_path}",
        as_superuser_gui=True,
        gui_prompt=gui_prompt
    )
    # cmd_exec("visudo", "-f", f"{uninstaller_sudoers_path}", as_superuser=True)
    yield
    cmd_exec(f"rm", "-f", f"{uninstaller_sudoers_path}", as_superuser=True)

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


def dscl(*args, **kwargs):
    return cmd_exec(
        ".",
        **kwargs,
        strict_flags_after_args=True,
        executable="/usr/bin/dscl",
        flag_format="-{flag}",
    )

def pkgutil(*args, **kwargs):
    return cmd_exec(
        executable="/usr/sbin/pkgutil",
        *args,
        **kwargs
    )


def productsign(*args, **kwargs):
    return cmd_exec(
        executable="/usr/bin/productsign",
        *args,
        **kwargs
    )

def launchctl(*args, **kwargs):
    return cmd_exec(
        executable="/bin/launchctl",
        # as_superuser=True,
        *args,
        **kwargs
    )
