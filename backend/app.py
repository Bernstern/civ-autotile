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
}

def getTerrainNameFromNumber(val: int):
    return autotiler_pb2.AutoTilerMap.BaseTerrain.Name(val)

def oddr_to_axial(tile):
    # https://www.redblobgames.com/grids/hexagons/#conversions-offset
    q = tile.col - (tile.row - (tile.row & 1)) / 2
    r = tile.row
    return q, r

def getDistanceBetweenTiles(tile1: autotiler_pb2.AutoTilerMap.Tile, tile2: autotiler_pb2.AutoTilerMap.Tile):
    # https://www.redblobgames.com/grids/hexagons/#distances-axial
    a = oddr_to_axial(tile1)
    b = oddr_to_axial(tile2)
    return (abs(a[0] - b[0]) + abs(a[0] + a[1] - b[0] - b[1]) + abs(a[1] - b[1])) / 2


class YieldsCalculator:
    BaseTerrain = {
        "plains" : (1,1),
        "grassland" : (2,0),
        "desert" : (0,0),
        "tundra" : (1,0),
        "snow" : (0,0),
        "coast" : (1,0),
        "ocean" : (1,0),
        "plains_hills" : (1,2),
        "grassland_hills" : (2,1),
        "desert_hills" : (0,1),
        "tundra_hills" : (1,1),
        "snow_hills" : (0,1),
    }

    @classmethod
    def calculate_yields(cls, tile: autotiler_pb2.AutoTilerMap.Tile):
        terrain = autotiler_pb2.AutoTilerMap.BaseTerrain.Name(tile.baseTerrain).lower()
        base_yield = cls.BaseTerrain[terrain]

        return base_yield
    
    @classmethod
    def calculate_tile_value(cls, tile: autotiler_pb2.AutoTilerMap.Tile):
        food, production = cls.calculate_yields(tile)
        return food + production
    
class AutoTiler():
    class Strategies(Enum):
        MAX_CITIES = 1
        MAX_YIELD = 2

    def __init__(self, map):
        self.map = map
        self.num_tiles = map.rows * map.cols

    def calculate_yields(self):
        yields = []

        for i in range(self.num_tiles):
            yield_value = YieldsCalculator.calculate_tile_value(self.map.tiles[i])
            yields.append(yield_value)
            self.map.tiles[i].food, self.map.tiles[i].production = YieldsCalculator.calculate_yields(self.map.tiles[i])

            # TODO: Add weight to yields
            self.map.tiles[i].yieldValue = yield_value

        self.lower_yield, self.upper_yield = min(yields), max(yields)
        print(f"Yields: {self.lower_yield} - {self.upper_yield}")

    def optimize(self, strategy: Strategies):
        # First go through each tile and update the yields
        self.calculate_yields()

        # Setup the model
        model = cp_model.CpModel()

        # Variables
        cities = [model.NewBoolVar('city_%i' % i) for i in range(self.num_tiles)]
        city_yield = [model.NewIntVar(self.lower_yield, self.upper_yield, f'city_yield_{i}') for i in range(self.num_tiles)]

        # Constraint: No cities on invalid tiles
        for i in range(self.num_tiles):
            if self.map.tiles[i].baseTerrain in INVALID_BASE_TERRAIN:
                model.Add(cities[i] == 0)

        # Constraint: No cities within 3 tiles of each other
        for i in range(self.num_tiles):
            for j in range(self.num_tiles):
                if 1 <= getDistanceBetweenTiles(self.map.tiles[i], self.map.tiles[j]) <= 3:
                    model.Add(cities[i] + cities[j] <= 1)

        # Objective: maximize total yield
        total_yield = model.NewIntVar(self.lower_yield, self.upper_yield * len(cities), 'total_yield')
        for i in range(self.num_tiles):
            model.Add(city_yield[i] == cities[i] * self.map.tiles[i].yieldValue)
        model.Add(total_yield == sum(city_yield))

        # Objective: Maximize number of cities
        model.Maximize(total_yield)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Print result
        optimized_min_yield = solver.ObjectiveValue()

        if status == cp_model.OPTIMAL:
            print(f'Optimal solution found w/ {optimized_min_yield} total yield.')
        else:
            print('No optimal solution found.')

        cities_placed = [i for i in range(self.num_tiles) if solver.Value(cities[i]) == 1]
        print(cities_placed)

        # Go through the map and add city improvement
        print(f"Added {sum(solver.Value(cities[i]) for i in range(self.num_tiles))} cities")
        for i in range(self.num_tiles):
            if solver.Value(cities[i]) == 1:
                self.map.tiles[i].improvement = autotiler_pb2.AutoTilerMap.Improvement.CITY


@app.route("/", methods=['POST']) 
def home():
    start_time = time.time()
    parser = reqparse.RequestParser()
    parser.add_argument('data', help="Data to be processed", location='json')
    args = parser.parse_args()

    payload = bytes(json.loads(args['data']))
    map = autotiler_pb2.AutoTilerMap()
    map.ParseFromString(payload)

    optimizer = AutoTiler(map)
    optimizer.optimize(AutoTiler.Strategies.MAX_YIELD)

    # Serialize the map and return it
    print(f"Total time: {time.time() - start_time:.2f}s")
    response = map.SerializeToString()
    return response

app.run(port=5000, debug=True)
