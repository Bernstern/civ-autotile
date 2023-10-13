import 'package:autotiler/gen/protobuf/autotiler.pb.dart';
import 'package:flutter/material.dart';

List<Color> colorsList = [
  Colors.red,
  Colors.green,
  Colors.blue,
  Colors.yellow,
  Colors.orange,
  Colors.purple,
  Colors.pink,
  Colors.teal,
  Colors.cyan,
  Colors.amber,
  Colors.indigo,
  Colors.lime,
  Colors.brown,
  Colors.grey,
  Colors.deepOrange,
  Colors.deepPurple,
  Colors.lightBlue,
  Colors.lightGreen,
  Colors.blueGrey,
  Colors.redAccent,
];

class TileWidget extends StatefulWidget {
  final AutoTilerMap_Tile tile;
  final Function setHoveredCity;
  final int hoveredCity;

  const TileWidget(
      {super.key,
      required this.tile,
      required this.setHoveredCity,
      required this.hoveredCity});

  @override
  _TileWidgetState createState() => _TileWidgetState();
}

class _TileWidgetState extends State<TileWidget> {
  bool isHovered = false;

  @override
  Widget build(BuildContext context) {
    // Create yield icons for food and production
    var yields = <Widget>[];
    isHovered = widget.tile.owner == widget.hoveredCity;

    AutoTilerMap_Tile tile = widget.tile;

    final tileYields = {
      "food": tile.food,
      "production": tile.production,
      "science": tile.science,
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

    print("rendering");

    return MouseRegion(
      onEnter: (_) {
        widget.setHoveredCity(tile.owner);
        // setState(() {});
      },
      onExit: (_) {
        widget.setHoveredCity(-2);
        // setState(() {});
      },
      child: Stack(
        alignment: Alignment.center,
        children: [
          Image.asset(
            "base/${tile.baseTerrain.name.toLowerCase()}.jpg",
            fit: BoxFit.cover,
          ),
          if (tile.improvement != AutoTilerMap_Improvement.NONE)
            Image.asset(
              "icons/${tile.improvement.name.toLowerCase()}.jpg",
            ),
          Opacity(
              opacity: .6,
              child:
                  Container(color: colorsList[tile.owner % colorsList.length])),
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
      ),
    );
  }
}
