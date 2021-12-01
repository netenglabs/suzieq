from faker import Faker
import argparse
import yaml
from suzieq.inventory_provider.tests.generators.base_generators \
    .source_generator import SourceGenerator
from os.path import isfile, join, dirname, abspath

DATA_GENERATOR_DIRECTORY = dirname(abspath(__file__))
SOURCE_GENERATOR_DIRECTORY = join(DATA_GENERATOR_DIRECTORY, "generator")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c", "--config", help="data_generator configuration file",
        required=True
    )
    args = parser.parse_args()

    config_file = args.config

    if not isfile(config_file):
        raise ValueError(f"File {config_file} doesn't exists")

    with open(config_file, "r") as f:
        config_data = yaml.safe_load(f.read())

    base_gen_pkg = "suzieq.inventory_provider.tests.generators.base_generators"
    base_gen_classes = SourceGenerator.get_plugins(base_gen_pkg)

    fake = Faker()
    seed = config_data.get("seed", None)
    if seed is not None:
        Faker.seed(seed)

    for macro_gen_type, generators in \
            config_data.get("generators", {}).items():

        gen_names = []

        for gen in generators:
            gen_type = gen.get("type", "")
            if not gen_type:
                raise RuntimeError("You must specify a type "
                                   "for each generator")

            gen_name = gen.get("name", "default")
            if gen_name in gen_names:
                raise RuntimeError("generator names must be unique")
            gen_names.append(gen_name)

            base_gen_class = base_gen_classes.get(macro_gen_type, None)
            if not base_gen_class:
                raise AttributeError(
                    f"Unknown generator type {macro_gen_type}")

            gens_pkg = f"suzieq.inventory_provider.tests.generators.{macro_gen_type}"
            gen_classes = base_gen_class.get_plugins(gens_pkg)

            gen_class = gen_classes.get(gen_type, None)

            if not gen_class:
                raise RuntimeError("Unable to find a generator "
                                   "class called {}".format(gen_type))

            gen_data = gen.get("data", {})

            gen_obj = gen_class(gen_name, fake, gen_data)
            gen_obj.generate()


if __name__ == "__main__":
    main()
