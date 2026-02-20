import json
import sys
from output import print_results
from clusters import Cluster
from tests.types import TestEntity

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python table.py <output_file.json>")
        sys.exit(1)

    output_file = sys.argv[1]

    with open(output_file, "r") as f:
        output_content = json.load(f)

    results_map = output_content["results_map"]
    sources = [TestEntity(**x) for x in output_content["sources"]]
    destinations = [TestEntity(**x) for x in output_content["destinations"]]
    clusters = {
        k: Cluster(**v, fetch_initial_data=False)
        for k, v in output_content["clusters"].items()
    }

    print_results(results_map, sources, destinations, clusters)
