import argparse
import json
from dataclasses import asdict
from input import load_config_or_exit
from clusters import load_clusters
from tests.execution import run_tests
from tests.context import TestManager
from tests.martrix import generate_test_matrix, generate_test_suite
from output import print_results, create_results_map, print_test_summary


def main(
    config_file: str,
    verbose: bool = False,
    output_path: str | None = None,
) -> None:
    config = load_config_or_exit(config_file)

    clusters = load_clusters(config)
    sources, destinations = generate_test_matrix(clusters)
    tests_suites = generate_test_suite(config.tests, clusters)

    for test_name, test_resources in tests_suites:
        with TestManager(test_name, test_resources):
            results = run_tests(sources, destinations, clusters)
            results_map = create_results_map(results)

            if verbose:
                print_test_summary(results)

            if output_path:
                with open(output_path, "w") as f:
                    json.dump(
                        {
                            "results_map": results_map,
                            "sources": [asdict(x) for x in sources],
                            "destinations": [asdict(x) for x in destinations],
                            "clusters": {
                                name: cluster.to_dict()
                                for name, cluster in clusters.items()
                            },
                        },
                        f,
                        indent=2,
                    )

            print_results(results_map, sources, destinations, clusters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run cross-cluster network tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-o", "--output", metavar="PATH", help="Output path")
    parser.add_argument("config_file", help="Path to config file")
    args = parser.parse_args()

    main(args.config_file, verbose=args.verbose, output_path=args.output)
