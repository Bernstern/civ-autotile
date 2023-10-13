#!/usr/bin/env python3

from enum import Enum
import json
import time
from flask import Flask, request
from flask_cors import CORS, cross_origin
from flask_restful import reqparse
from ortools.sat.python import cp_model


import autotiler_pb2

app = Flask(__name__)
cors = CORS(app)

INVALID_BASE_TERRAIN = {
    autotiler_pb2.AutoTilerMap.BaseTerrain.COAST,
    autotiler_pb2.AutoTilerMap.BaseTerrain.OCEAN,
    autotiler_pb2.AutoTilerMap.BaseTerrain.MOUNTAINS,
}

MIN_DISTANCE_BETWEEN_CITIES = 3


def getTerrainNameFromNumber(val: int):
    return autotiler_pb2.AutoTilerMap.BaseTerrain.Name(val)


def oddr_to_cube(tile):
    # https://www.redblobgames.com/grids/hexagons/#conversions-offset
    x = tile.col - (tile.row - (tile.row & 1)) // 2
    z = tile.row
    y = -x - z
    return x, y, z


def cube_subtract(a, b):
    # https://www.redblobgames.com/grids/hexagons/#distances-cube
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def cube_add(a, b):
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def cube_direction(direction: int):
    dirs = [(1, 0, -1), (1, -1, 0), (0, -1, 1), (-1, 0, 1), (-1, +1, 0), (0, 1, -1)]
    return dirs[direction]


def cube_neighbor(cube_coord, direction: int):
    return cube_add(cube_coord, cube_direction(direction))


def cube_scale(cube_coords, scale):
    return tuple(c * scale for c in cube_coords)


def cube_distance(a, b):
    vec = cube_subtract(oddr_to_cube(a), oddr_to_cube(b))
    return (abs(vec[0]) + abs(vec[1]) + abs(vec[2])) // 2


class YieldsCalculator:
    BaseTerrain = {
        "plains": (1, 1),
        "grassland": (2, 0),
        "desert": (0, 0),
        "tundra": (1, 0),
        "snow": (0, 0),
        "coast": (1, 0),
        "ocean": (1, 0),
        "plains_hills": (1, 2),
        "grassland_hills": (2, 1),
        "desert_hills": (0, 1),
        "tundra_hills": (1, 1),
        "snow_hills": (0, 1),
        "mountains": (0, 0),
        "grassland_floodplains": (2, 0),
        "desert_floodplains": (3, 0),
        "plains_floodplains": (1, 1),
    }

    Features = {
        "empty": (0, 0),
        "woods": (0, 1),
        "rainforest": (1, 0),
        "marsh": (1, 0),
        "oasis": (3, 0),
        "geothermal_fissure": (0, 0),
        "volcanic_soil": (0, 0),
        "reef": (1, 1),
    }

    Resources = {
        "clear": (0, 0),
        "bananas": (1, 0),
        "copper": (0, 0),
        "cattle": (1, 0),
        "crabs": (0, 0),
        "deer": (0, 1),
        "fish": (1, 0),
        "maize": (0, 0),
        "rice": (1, 0),
        "sheep": (0, 1),
        "stone": (0, 1),
        "wheat": (1, 0),
        "amber": (0, 0),
        "cinnamon": (0, 0),
        "citrus": (2, 0),
        "cloves": (0, 0),
        "cocoa": (0, 0),
        "coffee": (0, 0),
        "cosmetics": (0, 0),
        "cotton": (0, 0),
        "dyes": (0, 0),
        "diamonds": (0, 0),
        "furs": (1, 0),
        "gypsum": (0, 1),
        "honey": (2, 0),
        "incense": (0, 0),
        "ivory": (0, 1),
        "jade": (0, 0),
        "jeans": (0, 0),
        "marble": (0, 0),
        "mercury": (0, 0),
        "olives": (0, 1),
        "pearls": (0, 0),
        "perfume": (0, 0),
        "salt": (1, 0),
        "silk": (0, 0),
        "silver": (0, 0),
        "spices": (2, 0),
        "sugar": (2, 0),
        "tea": (0, 0),
        "tobacco": (0, 0),
        "toys": (0, 0),
        "truffles": (0, 0),
        "turtles": (0, 0),
        "whales": (0, 1),
        "wine": (1, 0),
        "horses": (1, 1),
        "iron": (0, 0),
        "niter": (1, 1),
        "coal": (0, 2),
        "oil": (0, 3),
        "aluminum": (0, 0),
        "uranium": (0, 2),
    }

    @classmethod
    def calculate_yields(cls, tile: autotiler_pb2.AutoTilerMap.Tile):
        terrain = autotiler_pb2.AutoTilerMap.BaseTerrain.Name(tile.baseTerrain).lower()
        base_yield = cls.BaseTerrain[terrain]

        feature = autotiler_pb2.AutoTilerMap.Feature.Name(tile.feature).lower()
        feature_yield = cls.Features[feature]

        if hasattr(tile, "resource"):
            resource = autotiler_pb2.AutoTilerMap.Resource.Name(tile.resource).lower()
            resource_yield = cls.Resources[resource]
        else:
            resource_yield = (0, 0)

        # Sum the yields in the tuple
        food = sum([base_yield[0], feature_yield[0], resource_yield[0]])
        production = sum([base_yield[1], feature_yield[1], resource_yield[1]])

        return (food, production)


class AutoTiler:
    class Strategies(Enum):
        MAX_CITIES = 1
        MAX_YIELD = 2
        MAX_FOOD = 3
        MAX_PRODUCTION = 4

    def __init__(self, map):
        self.map = map
        self.num_tiles = map.rows * map.cols

        # First go through and prefetch each tile and store it's cube coordinates mapping to its id
        self.cube_to_id = {}
        for i in range(self.num_tiles):
            self.cube_to_id[oddr_to_cube(self.map.tiles[i])] = i

        # Go through and calculate the immediate neighbors for each tile
        self.neighbors = {}
        for i in range(self.num_tiles):
            tile_neighbors = self.fetch_ring(self.map.tiles[i], radius=1)
            self.neighbors[i] = [
                self.cube_to_id[coord]
                for coord in tile_neighbors
                if coord in self.cube_to_id
            ]

    def fetch_ring(self, tile, radius):
        # First get the cube coordinates of the tile
        center = oddr_to_cube(tile)

        if radius == 0:
            return [center]

        results = []

        hex = cube_add(center, cube_scale(cube_direction(4), radius))
        for i in range(6):
            for j in range(radius):
                results.append(hex)
                hex = cube_neighbor(hex, i)

        return results

    def fetch_cumulative_ring(self, tile, radius: int):
        # DOESNT INCLUDE THE CENTER
        # https://www.redblobgames.com/grids/hexagons/#rings-spiral
        results = []
        for i in range(1, radius + 1):
            results += self.fetch_ring(tile, i)
        return results

    def calculate_campus_adjacency(self, neighbors):
        # Go through each neighbor and add on adjacency bonuses
        adjacency = 0

        for coord in neighbors:
            tile_id = self.cube_to_id.get(coord, None)

            if tile_id is None:
                continue

            neighbor = self.map.tiles[tile_id]

            # +2 science from Great Barrier Reef or Pamukkale TODO

            # +2 science from geothermal fissure + reef
            if neighbor.feature in [
                autotiler_pb2.AutoTilerMap.Feature.GEOTHERMAL_FISSURE,
                autotiler_pb2.AutoTilerMap.Feature.REEF,
            ]:
                adjacency += 2

            # +1 science for a mountain
            if neighbor.baseTerrain == autotiler_pb2.AutoTilerMap.BaseTerrain.MOUNTAINS:
                adjacency += 1

            # +0.5 science for each adjacent district/improvement
            if neighbor.improvement != autotiler_pb2.AutoTilerMap.Improvement.NONE:
                adjacency += 0.5

            # +0.5 for each adjacent rainforest
            if neighbor.feature == autotiler_pb2.AutoTilerMap.Feature.RAINFOREST:
                adjacency += 0.5

        return adjacency

    def calculate_yields(self, strategy: Strategies = Strategies.MAX_YIELD):
        yields = []

        for i in range(self.num_tiles):
            if strategy == AutoTiler.Strategies.MAX_FOOD:
                yield_value = YieldsCalculator.calculate_yields(self.map.tiles[i])[0]
            elif strategy == AutoTiler.Strategies.MAX_PRODUCTION:
                yield_value = YieldsCalculator.calculate_yields(self.map.tiles[i])[1]
            # Default to max yield
            else:
                yield_value = sum(YieldsCalculator.calculate_yields(self.map.tiles[i]))

            yields.append(yield_value)
            (
                self.map.tiles[i].food,
                self.map.tiles[i].production,
            ) = YieldsCalculator.calculate_yields(self.map.tiles[i])

            # TODO: Add weight to yields
            self.map.tiles[i].yieldValue = yield_value

        self.lower_yield, self.upper_yield = min(yields), max(yields)
        print(f"Yields: {self.lower_yield} - {self.upper_yield}")

    def optimize_cities(self, strategy: Strategies):
        # First go through each tile and update the yields
        self.calculate_yields(strategy)

        # Setup the model
        model = cp_model.CpModel()

        # Variables
        cities = [model.NewBoolVar("city_%i" % i) for i in range(self.num_tiles)]
        city_yield = [
            model.NewIntVar(self.lower_yield, self.upper_yield, f"city_yield_{i}")
            for i in range(self.num_tiles)
        ]

        # Constraint: No cities on invalid tiles
        for i in range(self.num_tiles):
            if self.map.tiles[i].baseTerrain in INVALID_BASE_TERRAIN:
                model.Add(cities[i] == 0)

        # Constraint: No cities within 3 tiles of each other
        #   be careful here to not restrict a tile against itself, almost got caught on that with cumulative ring generation
        for i in range(self.num_tiles):
            ring = self.fetch_cumulative_ring(
                self.map.tiles[i], radius=MIN_DISTANCE_BETWEEN_CITIES
            )
            for coord in ring:
                tile_id = self.cube_to_id.get(coord, None)
                if tile_id is None:
                    continue  # This means that the tile is off our map
                model.Add(cities[i] + cities[tile_id] <= 1)

        # Objective: Maximize number of cities
        if strategy == AutoTiler.Strategies.MAX_YIELD:
            model.Maximize(sum(cities))
        else:
            # Objective: maximize total value
            total_yield = model.NewIntVar(
                self.lower_yield, self.upper_yield * len(cities), "total_yield"
            )
            for i in range(self.num_tiles):
                model.Add(city_yield[i] == cities[i] * self.map.tiles[i].yieldValue)
            model.Add(total_yield == sum(city_yield))

            model.Maximize(total_yield)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Print result
        optimized_min_yield = solver.ObjectiveValue()

        if status == cp_model.OPTIMAL:
            print(f"Optimal solution found w/ {optimized_min_yield} total value.")
        else:
            print("No optimal solution found.")

        # Go through the map and add city improvement
        print(
            f"Added {sum(solver.Value(cities[i]) for i in range(self.num_tiles))} cities"
        )
        for i in range(self.num_tiles):
            if solver.Value(cities[i]) == 1:
                self.map.tiles[
                    i
                ].improvement = autotiler_pb2.AutoTilerMap.Improvement.CITY

    def optimize_campuses(self):
        # Setup the model
        model = cp_model.CpModel()

        # Go through and calculate initial adjacency for each tile
        base_adjacency = []
        for i in range(self.num_tiles):
            neighbors = self.fetch_ring(self.map.tiles[i], radius=1)
            base_adjacency.append(self.calculate_campus_adjacency(neighbors))

        # For our purposes we have to double this adjacency since the model only likes ints
        base_adjacency = [int(adj * 2) for adj in base_adjacency]

        # Max tile science is the best base adjacency + 6 surrounding campuses (remember, doubled)
        max_tile_science = max(base_adjacency) + 6

        # Variables
        campus = [model.NewBoolVar("campus_%i" % i) for i in range(self.num_tiles)]
        campus_adj = [
            model.NewIntVar(0, max_tile_science, f"campus_adj_{i}")
            for i in range(self.num_tiles)
        ]

        # Simple constraint: No campuses on invalid tiles or on cities
        for i in range(self.num_tiles):
            if (
                self.map.tiles[i].baseTerrain in INVALID_BASE_TERRAIN
                or self.map.tiles[i].improvement
                == autotiler_pb2.AutoTilerMap.Improvement.CITY
            ):
                model.Add(campus[i] == 0)

        # Calculate adjacny benefits and add to total science
        for i in range(self.num_tiles):
            adjacency = 0

            # Get the immediate ring, then their ids
            neighbors = self.fetch_ring(self.map.tiles[i], radius=1)
            neighbor_ids = [
                self.cube_to_id.get(coord, None)
                for coord in neighbors
                if self.cube_to_id.get(coord, None) is not None
            ]

            # Then calculate adjacency as the sum of base + neighbors (pretty much adding 1 for each neighbor that has a campus, again remember, doubled)
            for neighbor_id in neighbor_ids:
                adjacency += campus[neighbor_id]

            # Add the adjacency to the model
            model.Add(campus_adj[i] == base_adjacency[i] + adjacency)

        # Objective: Maximize total science from base adj + other campuses
        total_science = model.NewIntVar(
            0, max(base_adjacency) * self.num_tiles, "total_science"
        )
        model.Add(total_science == sum(campus_adj))
        model.Maximize(total_science)

        # Ownership Variables: Each campus has a unique owner (city)
        ownership = [
            model.NewIntVar(0, self.num_tiles, f"ownership_{i}")
            for i in range(self.num_tiles)
        ]

        # Distance Constraints: Ensure campuses are within the specified distance of their owners
        for i in range(self.num_tiles):
            for j in range(self.num_tiles):
                distance_to_owner = [
                    model.NewBoolVar(f"distance_{i}_to_owner_{j}")
                    for i in range(self.num_tiles)
                ]
                for j in range(3):
                    model.Add(
                        sum(distance_to_owner[i] for i in range(3)) <= 1
                    )  # Ensure at most one distance
                model.Add(ownership[i] == j).OnlyEnforceIf(distance_to_owner[i])
                model.Add(ownership[i] != j).OnlyEnforceIf(distance_to_owner[i].Not())

        # Each campus has a unique owner
        for i in range(self.num_tiles):
            model.Add(sum(ownership[i] == j for j in range(self.num_tiles)) == 1)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL:
            print(f"Optimal solution found w/ {solver.ObjectiveValue()} total science.")

        # Go through and log each added campus and it's adjacency
        for i in range(self.num_tiles):
            if solver.Value(campus[i]) == 1:
                print(f"Campus at {self.map.tiles[i].row}, {self.map.tiles[i].col}")
                print(f"Adjacency: {solver.Value(campus_adj[i]) / 2}")
                # self.map.tiles[
                #     i
                # ].improvement = autotiler_pb2.AutoTilerMap.Improvement.CAMPUS

                # To send it back we need to divide by 2 then cast to int since our proto requires ints
                self.map.tiles[i].science = int(solver.Value(campus_adj[i]) / 2)

            # Update ownership
            self.map.tiles[i].owner = solver.Value(ownership[i])

    def maximize_city_regions(self):
        model = cp_model.CpModel()
        num_tiles = self.num_tiles
        valid_tiles = range(num_tiles)

        cities = [
            i
            for i in valid_tiles
            if self.map.tiles[i].improvement
            == autotiler_pb2.AutoTilerMap.Improvement.CITY
        ]
        num_cities = len(cities)

        helper_bools = [
            [model.NewBoolVar(f"helper_{i}_{j}") for j in valid_tiles]
            for i in valid_tiles  # helper[i][j] = 1 if tile i is owned by city j
        ]

        # Objective: Maximize average tile count per city
        tile_count = [
            model.NewIntVar(0, num_tiles, f"tile_count_city_{i}")
            for i in range(num_cities)
        ]
        print(len(tile_count))

        for city_idx in range(num_cities):
            city = cities[city_idx]
            bools = [helper_bools[j][city] for j in valid_tiles]
            model.Add(tile_count[city_idx] == sum(bools))

        min_tile_count = model.NewIntVar(0, num_tiles, "min_tile_count")
        model.AddMinEquality(min_tile_count, tile_count)
        model.Maximize(min_tile_count)

        # Identity + Range constraint: Tiles must be within 3 tiles of their owner and cities own themselves
        for i in valid_tiles:
            for j in cities:
                if i == j:
                    model.Add(helper_bools[i][j] == 1)
                else:
                    distance = cube_distance(self.map.tiles[i], self.map.tiles[j])
                    if distance > 3:
                        model.Add(helper_bools[i][j] == 0)
                    else:
                        model.Add(helper_bools[i][j] <= 1)

        # Constraint: Each tile only has one owner
        for i in valid_tiles:
            model.Add(sum(helper_bools[i]) <= 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status != cp_model.OPTIMAL:
            raise Exception("No optimal solution found.")

        print(
            f"Optimal solution found with {num_cities} cities and min tile count of {solver.Value(min_tile_count)}"
        )

        total = 0
        for city in range(num_cities):
            print(f"City {cities[city]} owns {solver.Value(tile_count[city])} tiles")
            total += solver.Value(tile_count[city])
        print(f"Total tiles: {total}")

        # Update ownership of each tile
        for i in valid_tiles:
            # Find the owner of this tile, will be the index of the bool which is true
            vals = []
            for j in valid_tiles:
                vals.append(solver.Value(helper_bools[i][j]))
            if 1 not in vals:
                self.map.tiles[i].owner = -1
                continue
            self.map.tiles[i].owner = solver.Value(vals.index(1))


@app.route("/", methods=["POST"])
def home():
    start_time = time.time()
    parser = reqparse.RequestParser()
    parser.add_argument("data", help="Data to be processed", location="json")
    args = parser.parse_args()

    payload = bytes(json.loads(args["data"]))
    map = autotiler_pb2.AutoTilerMap()
    map.ParseFromString(payload)

    optimizer = AutoTiler(map)
    optimizer.optimize_cities(AutoTiler.Strategies.MAX_CITIES)
    # optimizer.optimize_campuses()
    optimizer.maximize_city_regions()

    # Serialize the map and return it
    print(f"Total time: {time.time() - start_time:.2f}s")
    response = map.SerializeToString()
    return response


app.run(port=5000, debug=True)
