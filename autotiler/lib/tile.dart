import 'package:autotiler/gen/protobuf/autotiler.pb.dart';
import 'package:flutter/material.dart';

class Tile extends StatefulWidget {
  final AutoTilerMap_Tile tile;

  const Tile({super.key, required this.tile});

  @override
  State<StatefulWidget> createState() => _Tile();
}

class _Tile extends State<Tile> {
  bool isHovered = false;

  @override
  Widget build(BuildContext context) {
    // Create yield icons for food and production
    var yields = <Widget>[];

    final tileYields = {
      "food": widget.tile.food,
      "production": widget.tile.production,
      "science": widget.tile.science,
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

    AutoTilerMap_Tile tile = widget.tile;

    return Stack(
      alignment: Alignment.center,
      children: [
        Image.asset(
          "base/${tile.baseTerrain.name.toLowerCase()}.jpg",
          fit: BoxFit.cover,
        ),
        if (widget.tile.improvement != AutoTilerMap_Improvement.NONE)
          Image.asset(
            "icons/${tile.improvement.name.toLowerCase()}.jpg",
          ),
        Opacity(
            opacity: (tile.owner == -1) ? 0 : 0.5,
            child: Container(color: Colors.black)),
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
                  if (tile.feature != AutoTilerMap_Feature.EMPTY)
                    Image.asset(
                      "features/${tile.feature.name.toLowerCase()}.jpg",
                    ),
                  if (tile.resource != AutoTilerMap_Resource.CLEAR)
                    Image.asset(
                      "resources/${tile.resource.name.toLowerCase()}.jpg",
                    ),
                ],
              ),
            ),
          ],
        ),
        // Text(_tile.owner.toString()),
      ],
    );
  }
}
