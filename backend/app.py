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


def oddr_to_axial(tile):
    # https://www.redblobgames.com/grids/hexagons/#conversions-offset
    q = tile.col - (tile.row - (tile.row & 1)) / 2
    r = tile.row
    return q, r


def oddr_to_cube(tile):
    # https://www.redblobgames.com/grids/hexagons/#conversions-offset
    x = tile.col - (tile.row - (tile.row & 1)) / 2
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


def getDistanceBetweenTiles(
    tile1: autotiler_pb2.AutoTilerMap.Tile, tile2: autotiler_pb2.AutoTilerMap.Tile
):
    # https://www.redblobgames.com/grids/hexagons/#distances-axial
    a = oddr_to_axial(tile1)
    b = oddr_to_axial(tile2)
    return (abs(a[0] - b[0]) + abs(a[0] + a[1] - b[0] - b[1]) + abs(a[1] - b[1])) / 2


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

        # For our purposes we can take the floor of the adjacency so that the solver can work with ints
        base_adjacency = [int(adj) for adj in base_adjacency]

        # Max tile science is the best base adjacency + 6 surrounding campuses
        max_tile_science = max(base_adjacency) + 3

        # Variables
        campus = [model.NewBoolVar("campus_%i" % i) for i in range(self.num_tiles)]
        campus_adj = [
            model.NewIntVar(0, max_tile_science, f"campus_adj_{i}")
            for i in range(self.num_tiles)
        ]

        # Constraint: No campuses on invalid tiles or on cities
        for i in range(self.num_tiles):
            if (
                self.map.tiles[i].baseTerrain in INVALID_BASE_TERRAIN
                or self.map.tiles[i].improvement
                == autotiler_pb2.AutoTilerMap.Improvement.CITY
            ):
                model.Add(campus[i] == 0)

        # Constraint: For now lets say total campus count is one
        model.Add(sum(campus) == 10)

        # Objective: Maximize total science from base adj + other campuses
        total_science = model.NewIntVar(
            0, max(base_adjacency) * self.num_tiles, "total_science"
        )
        for i in range(self.num_tiles):
            model.Add(campus_adj[i] == campus[i] * base_adjacency[i])

        model.Add(total_science == sum(campus_adj))
        model.Maximize(total_science)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL:
            print(f"Optimal solution found w/ {solver.ObjectiveValue()} total science.")

        # Go through and log each added campus and it's adjacency
        for i in range(self.num_tiles):
            if solver.Value(campus[i]) == 1:
                print(f"Campus at {self.map.tiles[i].row}, {self.map.tiles[i].col}")
                print(f"Adjacency: {solver.Value(campus_adj[i]) }")
                self.map.tiles[
                    i
                ].improvement = autotiler_pb2.AutoTilerMap.Improvement.CAMPUS
                self.map.tiles[i].science = solver.Value(campus_adj[i])


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
    optimizer.optimize_campuses()

    # Serialize the map and return it
    print(f"Total time: {time.time() - start_time:.2f}s")
    response = map.SerializeToString()
    return response


app.run(port=5000, debug=True)
