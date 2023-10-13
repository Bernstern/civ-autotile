import 'dart:math';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:flutter/material.dart';
import 'package:hexagon/hexagon.dart';
import 'dart:convert';

import 'package:autotiler/gen/protobuf/autotiler.pb.dart';

typedef CivMap = Map<Record, Tile>;

void main() {
  runApp(const MyApp());
}

Future<http.Response> queryBackend(Uint8List data) async {
  return http.post(
      Uri.parse(
        "http://127.0.0.1:5000/",
      ),
      headers: <String, String>{
        'Content-Type': 'application/json; charset=UTF-8',
        'Access-Control-Allow-Origin': '*'
      },
      body: jsonEncode(<String, Uint8List>{
        'data': data,
      }));
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Civ AutoTiler',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const MyHomePage(),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({
    super.key,
  });

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class Tile {
  late AutoTilerMap_Tile _tile;
  late Color _color;

  Tile(int col, int row, AutoTilerMap_BaseTerrain terrain,
      AutoTilerMap_Feature feature) {
    _tile = AutoTilerMap_Tile(
        row: row,
        col: col,
        baseTerrain: terrain,
        improvement: AutoTilerMap_Improvement.NONE,
        feature: feature);
  }

  Tile.fromTile(AutoTilerMap_Tile tile) {
    _tile = tile;
  }

  String? get baseTerrainName {
    return _tile.baseTerrain.name.toLowerCase();
  }

  Stack get image {
    // Create yield icons for food and production
    var yields = <Widget>[];

    final tileYields = {
      "food": _tile.food,
      "production": _tile.production,
      "science": _tile.science,
    };

    tileYields.forEach((name, yield) {
      for (int i = 0; i < yield; i++) {
        yields.add(
          Flexible(
            child: Image.asset(
              "icons/$name.jpg",
            ),
          ),
        );
      }
    });

    return Stack(
      alignment: Alignment.center,
      children: [
        // Image.asset(
        //   "base/$baseTerrainName.jpg",
        //   fit: BoxFit.cover,
        // ),
        if (_tile.improvement != AutoTilerMap_Improvement.NONE)
          Image.asset(
            "icons/${_tile.improvement.name.toLowerCase()}.jpg",
          ),
        Opacity(
            opacity: (_tile.owner == -1) ? 0 : .5,
            child: Container(color: _color)),
        Column(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            const Row(),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: yields,
            ),
            SizedBox(
              height: 40,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (_tile.feature != AutoTilerMap_Feature.EMPTY)
                    Image.asset(
                      "features/${_tile.feature.name.toLowerCase()}.jpg",
                    ),
                  if (_tile.resource != AutoTilerMap_Resource.CLEAR)
                    Image.asset(
                      "resources/${_tile.resource.name.toLowerCase()}.jpg",
                    ),
                ],
              ),
            ),
          ],
        ),
        Text(_tile.owner.toString()),
      ],
    );
  }
}

class _MyHomePageState extends State<MyHomePage> {
  CivMap _tiles = {};
  Future<CivMap>? _tilesFuture;
  final int _rows = 12;
  final int _columns = 12;

  CivMap convertToCivMap(AutoTilerMap map) {
    CivMap tiles = {};

    // Get the total number of cities so we can color the tiles
    int totalCities = 0;
    for (AutoTilerMap_Tile tile in map.tiles) {
      totalCities = max(tile.owner, totalCities);
    }

    for (AutoTilerMap_Tile tile in map.tiles) {
      (int, int) coordinate = (tile.col, tile.row);
      tiles[coordinate] = Tile.fromTile(tile);
      tiles[coordinate]?._color = Color.fromARGB(255, 50,
          255 * tile.owner ~/ totalCities, 255 * tile.owner ~/ totalCities);
    }
    return tiles;
  }

  void generateTiles() {
    // Generate a map of tiles using offset hexagon coordinates storing the coord in the key as a record

    // Fix the random seed for now
    var rand = Random(1);

    for (int row = 0; row < _rows; row++) {
      for (int col = 0; col < _columns; col++) {
        (int, int) coordinate = (col, row);

        // Pick a random terrain TODO: no randoms
        AutoTilerMap_BaseTerrain terrain = AutoTilerMap_BaseTerrain
            .values[rand.nextInt(AutoTilerMap_BaseTerrain.values.length)];

        // Pick a random feature: whatever it might be impossible
        AutoTilerMap_Feature feature = AutoTilerMap_Feature.EMPTY;
        if (rand.nextInt(100) > 90) {
          feature = AutoTilerMap_Feature
              .values[rand.nextInt(AutoTilerMap_Feature.values.length)];
        }

        // Throw in some resources sometimes
        AutoTilerMap_Resource resource = AutoTilerMap_Resource.CLEAR;
        if (rand.nextInt(100) > 90) {
          resource = AutoTilerMap_Resource
              .values[rand.nextInt(AutoTilerMap_Resource.values.length)];
        }

        AutoTilerMap_Tile tile = AutoTilerMap_Tile(
            row: row,
            col: col,
            baseTerrain: terrain,
            improvement: AutoTilerMap_Improvement.NONE,
            feature: feature,
            resource: resource);

        _tiles[coordinate] = Tile.fromTile(tile);
      }
    }
  }

  Uint8List serializeToProto() {
    AutoTilerMap map = AutoTilerMap(
      rows: _rows,
      cols: _columns,
    );

    // Serialize the map to a bytearray to send to the server
    for (int row = 0; row < _rows; row++) {
      for (int col = 0; col < _columns; col++) {
        (int, int) coordinate = (col, row);
        Tile tile = _tiles[coordinate]!;
        map.tiles.add(tile._tile);
      }
    }

    return (map.writeToBuffer());
  }

  Future<Map<Record, Tile>> sendToBackend() async {
    generateTiles();
    Uint8List mapPayload = serializeToProto();
    var response = await queryBackend(mapPayload);

    if (response.statusCode == 200) {
      AutoTilerMap map = AutoTilerMap.fromBuffer(response.bodyBytes);
      return convertToCivMap(map);
    } else {
      throw Exception("Backend error");
    }
  }

  FutureBuilder<CivMap> buildFutureBuilder() {
    return FutureBuilder<CivMap>(
      future: _tilesFuture,
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          return HexagonOffsetGrid.oddPointy(
            columns: _columns,
            rows: _rows,
            buildChild: (col, row) {
              return AspectRatio(
                aspectRatio: HexagonType.POINTY.ratio,
                child: snapshot.data?[(col, row)]?.image,
              );
            },
          );
        } else if (snapshot.hasError) {
          return Text('wtf ${snapshot.error}');
        }

        return const CircularProgressIndicator();
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    _tilesFuture = sendToBackend();
    return Scaffold(
      floatingActionButton: ElevatedButton(
          onPressed: () {
            setState(() {
              _tilesFuture = sendToBackend();
            });
          },
          child: const Text("Generate")),
      body: Center(
        child: (_tilesFuture == null)
            ? const Text("No tiles")
            : buildFutureBuilder(),
      ),
    );
  }
}
