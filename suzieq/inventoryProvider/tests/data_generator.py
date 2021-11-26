from faker import Faker
import argparse
import yaml
from suzieq.inventoryProvider.tests.generator.sourceGenerator \
    import SourceGenerator
from os.path import isfile, join, dirname, abspath
from suzieq.inventoryProvider.utils \
    import get_class_by_path

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
        raise ValueError("File {} doesn't exists".format(config_file))

    with open(config_file, "r") as f:
        config_data = yaml.safe_load(f.read())

    fake = Faker()
    seed = config_data.get("seed", None)
    if seed is not None:
        Faker.seed(seed)

    for macro_gen_type, generators in \
            config_data.get("generators", {}).items():
        base_gen_type_name = SourceGenerator.__name__
        gen_dir = join(DATA_GENERATOR_DIRECTORY, macro_gen_type)

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
            gen_path = join(gen_dir, gen_type)
            gen_classes = get_class_by_path(
                gen_path,
                SOURCE_GENERATOR_DIRECTORY,
                base_gen_type_name
            )
            gen_type = gen_type.lower()

            gen_class = gen_classes.get(gen_type, None)
            if not gen_class:
                raise RuntimeError("Unable to find a generator "
                                   "class called {}".format(gen_type))

            gen_data = gen.get("data", {})

            gen_obj = gen_class(gen_name, fake, gen_data)
            gen_obj.generate()


if __name__ == "__main__":
    main()
