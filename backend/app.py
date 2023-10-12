#!/usr/bin/env python3

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
    a = oddr_to_axial(tile1)
    b = oddr_to_axial(tile2)
    return (abs(a[0] - b[0]) + abs(a[0] + a[1] - b[0] - b[1]) + abs(a[1] - b[1])) / 2

@app.route("/", methods=['POST']) 
def home():
    start_time = time.time()
    parser = reqparse.RequestParser()
    parser.add_argument('data', help="Data to be processed", location='json')
    args = parser.parse_args()

    payload = bytes(json.loads(args['data']))
    map = autotiler_pb2.AutoTilerMap()
    map.ParseFromString(payload)

    model = cp_model.CpModel()

    # Variables
    cities = [model.NewIntVar(0, 1, 'city_%i' % i) for i in range(map.rows * map.cols)]


    # Constraints: No cities on invalid tiles
    for i in range(map.rows * map.cols):
        if map.tiles[i].baseTerrain in INVALID_BASE_TERRAIN:
            # print(f"Blocking tile {i} from having a city [base terrain {map.tiles[i].baseTerrain}]]")
            model.Add(cities[i] == 0)

    # Constraints: No cities within 3 tiles of each other
    for i in range(map.rows * map.cols):
        for j in range(map.rows * map.cols):
            if 1 <= getDistanceBetweenTiles(map.tiles[i], map.tiles[j]) <= 3:
                model.Add(cities[i] + cities[j] <= 1)

    # Objective: Maximize number of cities
    model.Maximize(sum(cities))

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL:
        print('Optimal solution found!')
    else:
        print('No optimal solution found.')

    # Print out the solution.
    print(f"Able to build {solver.ObjectiveValue()} cities")

    # Go through the map and add city improvement
    for i in range(map.rows * map.cols):
        if solver.Value(cities[i]) == 1:
            map.tiles[i].improvement = autotiler_pb2.AutoTilerMap.Improvement.CITY

    # Serialize the map and return it
    print(f"Total time: {time.time() - start_time:.2f}s")
    response = map.SerializeToString()
    return response

app.run(port=5000, debug=True)
