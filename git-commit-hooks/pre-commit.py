#!/usr/bin/env python
import os
import sys
import subprocess
import pydocstyle
import platform
from termcolor import colored
_encoding = sys.getdefaultencoding()
"""
Installation
0. Install the following python packages
  - pylint
  - pep8
  - pydocstyle (for PEP257)
  - termcolor (to make it preeeeettty)
1. Move/Copy this file to .git/hooks/ in your repository root.
2. Make it executable: chmod +x .git/hooks/pre-commit
CHANGELOG
- filtering only for modification and additions, so moves don't fail
--
- pep8 is now running relative in Core/
--
- ignore windows related files on mac
- pydocstyle is now optional
--
- pylint also checks cc and tests to check for cyclic imports (with -j3)
- fixed config paths for pylint and setup.cfg
"""
def repo_root():
    p = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE)
    out, _ = p.communicate()
    return out.splitlines()[0].decode(_encoding)

def system(*args, **kwargs):
    kwargs.setdefault('stdout', subprocess.PIPE)
    proc = subprocess.Popen(args, **kwargs)
    out, err = proc.communicate()
    return out, proc.returncode

def perform_pydocstyle(files):
    errors, is_ok = pydocstyle.checker.check(files, select=pydocstyle.violations.conventions.pep257), True
    for error in errors:
        if is_ok:
             print(colored('WARNING', 'magenta', attrs=['blink']), 'Ensure existing documentation passes PEP257.')
        is_ok = False
        print(colored("{}:{}\t{}\t{}".format(error.filename, error.line, error.code, error.short_desc), 'yellow'))
        # print(error.context)
        # print(error.definition)
        # print(error.explain)
        # print(error.explanation)
        # print(error.lines)
        # print(error.message)
        # print(error.parameters)
        # print(error.short_desc)
        # print(error.source)
        
    if is_ok:
        print(colored('PASS', 'green'), 'Ensure existing documentation passes PEP257.')
        return True
    else:
        return True
    
def perform_pylint(files):
    exclusions = []
    if os.name == 'posix':
        exclusions.extend(['cifs.py', 'windows.py', 'windows_explorer.py'])
    if platform.system() != 'Darwin':
        exclusions.extend(['macos'])
    exclusions_string = '--ignore={}'.format(','.join(exclusions))
    folders = list(map(lambda x: os.path.join(repo_root(), "Core", x), ["cc", "tests"]))
    print("Checking folders %s" % folders)
    pylint_configuration_file = os.path.join(repo_root(), "Core", ".pylintrc")
    print("Using '%s' configuration file" % pylint_configuration_file)
    pylint_message_format='{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}'
    output, exitcode = system("pylint", "-j", "3", exclusions_string, "--rcfile=%s" % pylint_configuration_file, "--msg-template=%s" % pylint_message_format, "-r", "n", *folders)
    if exitcode != 0:
        print(colored('FAIL', 'red', attrs=['blink']), 'Ensure changed code passes pylint.')
        print(output.decode(_encoding))
        return False
    print(colored('PASS', 'green'), 'Ensure changed code passes pylint.')
    return True
    
def perform_pep8(files):
    pep8_configuration_file = os.path.join(repo_root(), "Core", "setup.cfg")
    core_dir =  os.path.join(repo_root(), "Core")
    print('pep8 config file: {}'.format(pep8_configuration_file))
    output, exitcode = system("pep8", "--config=%s" % pep8_configuration_file, *files,
        cwd=core_dir)
    if exitcode != 0:
        print(colored('FAIL', 'red', attrs=['blink']), 'Ensure changed code passes PEP8.')
        print(output.decode(_encoding))
        return False
    
    print(colored('PASS', 'green'), 'Ensure changed code passes PEP8.')
    return True
    
def perform_grep_for_pattern(pattern, files):
    files = [elem for elem in files if elem.startswith(os.path.join('Core', 'cc'))]
    print("Checking files {} for '{}' statements".format(files, pattern))
    output, exitcode = system("grep", "-H", "-n", pattern, *files)
    if exitcode == 0:
        print(colored('FAIL', 'red', attrs=['blink']), 'Ensure no "{}" statements are present.'.format(pattern))
        print(output.decode(_encoding))
        return False
    
    print(colored('PASS', 'green'), 'Ensure no "{}" statements are present.'.format(pattern))
    return True
    
if __name__ == '__main__':
  files, exitcode = system('git', 'diff-index', '--cached', 'HEAD', '--name-only', '--diff-filter=AM')
  assert exitcode == 0
  
  files = files.split(b"\n")
  changed_files = list(map(lambda x: x.decode(_encoding), filter(lambda x: len(x), files)))
  changed_python_files = list(filter(lambda x: x.endswith('.py') and x.startswith('Core'), changed_files))
  
  relative_to_core_py_files = [path.replace('Core/', '') for path in changed_python_files]

  print("Found %d changed python files to check." % len(changed_python_files))
  print("Repository root is at '%s'" % repo_root())
  
  if len(changed_files) == 0:
    print(colored("Nothing to check. No files found!", 'yellow'))
    sys.exit(0)
  if all([
        perform_pydocstyle(changed_python_files),
        perform_pep8(relative_to_core_py_files), 
        perform_pylint(changed_python_files),
        perform_grep_for_pattern('^\s*print(', changed_python_files)]):
    print(colored("Your commit looks good.", 'green'))
    sys.exit(0)
  else:
    print(colored("\nYour commit contains errors! Please fix them and try again!\n", 'red', attrs=['bold']))
    sys.exit(42)
    
