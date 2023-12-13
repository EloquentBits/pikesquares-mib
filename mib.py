#!/usr/bin/env python3
import logging
import json
import tomllib
import shutil
import xml.etree.ElementTree as ET

from argparse import ArgumentParser
from pathlib import Path

from utils import pkgbuild, productbuild, working_directory, installer

logger = logging.getLogger(__file__)
# logger.setLevel(logging.ERROR)
# logger.addHandler(logging.StreamHandler(stream=sys.stdout))
logging.basicConfig(
    format="(%(module)s) %(asctime)s [%(levelname)s] %(message)s"
)

from jinja2 import Environment, FileSystemLoader, select_autoescape, exceptions as jinja2_exc

resources_path = (Path("_files") / "Resources" / "en.lproj").resolve()
templates_path = Path("templates").resolve()
# working_directory = Path(__file__).parent


env = Environment(
    loader=FileSystemLoader(templates_path),
    autoescape=select_autoescape()
)

def fill_template(file_path, values: dict):
    tmpl_name = Path(file_path).name
    template = env.get_template(tmpl_name)
    # breakpoint()
    with open(file_path, "w") as file:
        logger.info(f"Processing template: {file_path}")
        file.write(
            template.render(**values)
        )


def fill_templates(tmpl_dir, values: dict):
    for file_path in Path(tmpl_dir).glob("**/*"):
        try:
            if file_path.is_dir() or file_path.suffix == ".png":
                continue
            fill_template(file_path, values=values)
        except jinja2_exc.TemplateNotFound:
            continue


def parse_args():
    parser = ArgumentParser(
        description="Makes application installer from config",
        usage="\n\nExample:\n\tmib2 --config mib.toml",
    )
    parser.add_argument(
        "-c", "--config",
        action="store",
        default="mib.toml",
        # required=True,
        help="mib json (or toml) config path"
    )
    return parser.parse_args()


def load_config(config_path="mib.json"):
    with open(config_path, "rb") as file:
        if config_path.suffix == ".json":
            return json.load(file)
        elif config_path.suffix == ".toml":
            return tomllib.load(file)
        else:
            import sys
            sys.stderr.write("This config is not supported! (only json, toml files are supported)\n")
            exit(1)

def modify_distribution_xml(file_path, params):
    tree = ET.parse(file_path)
    root = tree.getroot()
    for k, opt in params.items():
        if not root.findall(k):
            new_elem = ET.Element(k)
            if isinstance(opt, str):
                new_elem.text = opt
            elif isinstance(opt, bool):
                elem.text = str(opt).lower()
            else:
                new_elem.attrib.update(opt)
            root.append(new_elem)
        for elem in root.iter(k):
            if isinstance(opt, str):
                elem.text = str(opt)
            elif isinstance(opt, bool):
                elem.text = str(opt).lower()
            elif isinstance(opt, dict):
                for attr, val in opt.items():
                    if isinstance(val, bool):
                        elem.text = str(val).lower()
                    elem.set(attr, val)
    tree.write(file_path)

def working_dir_path(path, as_path: bool = False) -> str:
    resolved_path = (Path(__file__).parent / Path(path)).resolve()
    if as_path:
        return resolved_path
    return str(resolved_path)

def build_dir_path(path):
    build_dir = Path(__file__).parent / "build"
    build_dir.mkdir(exist_ok=True, parents=True)
    return str((build_dir / Path(path)).resolve())

def main():
    args = parse_args()
    config = load_config(config_path=Path(args.config))

    product_config = config.get("product", {})
    product_identifier = product_config.get("identifier")
    product_name = product_config.get("name")
    product_version = product_config.get("version")

    installer_config = product_config.get("installer", {})

    check_installer = installer_config.get("check-after-build", False)
    installer_name = installer_config.get("file-name")
    resources_dir = installer_config.get("resources-dir")

    distribution_params = installer_config.get("distribution")
    
    config_files = installer_config.get("files", [])
    packages_list = []
    for file in config_files:
        file_name = file.get("name")
        root = file.get("root")
        install_location = file.get("install-location")
        pkgbuild_params = dict(
            root=working_dir_path(root),
            identifier=f"{product_identifier}-{file_name}",
            version=product_version,
            install_location=install_location
        )
        if file.get("scripts-dir"):
            pkgbuild_params.update({'scripts': working_dir_path(file.get("scripts-dir"))})
        with working_directory("build"):
            pkgbuild(
                f"{product_name}-{file_name}.pkg",
                **pkgbuild_params
            )
        packages_list.append(f"{product_name}-{file_name}.pkg")

    # dist_xml_path = str((build_path / ).resolve())
    # breakpoint()
    # os.chdir(build_path)
    with working_directory("build"):
        productbuild(
            f"{product_name}-distribution.xml",
            packages=packages_list,
            synthesize=True
        )
        # modifying distribution xml
        modify_distribution_xml(
            f"{product_name}-distribution.xml",
            params=distribution_params
        )

    # fill html templates based on params
    fill_templates(
        working_dir_path(resources_path),
        values={'product': product_config}
    )
    
    with working_directory("build"):
        productbuild(
            f"{installer_name}.pkg",
            distribution=f"{product_name}-distribution.xml",
            resources=working_dir_path(resources_dir)
        )
    # print(f"{os.getcwd()=}") 
    
    working_dir_path(f"{installer_name}.pkg", as_path=True).unlink(missing_ok=True)
    shutil.move(build_dir_path(f"{installer_name}.pkg"), Path(__file__).parent)

    logger.info("Installer generating process finished")
    if check_installer:
        logger.info("Checking installer")
        installer(
            pkg=f"{installer_name}.pkg",
            target="/",
            dumplog=True
        )
    exit(0)


if __name__ == "__main__":
    main()
