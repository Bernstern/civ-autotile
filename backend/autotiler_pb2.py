# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: protobuf/autotiler.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x18protobuf/autotiler.proto\x12\tautotiler\"\xc2\x06\n\x0c\x41utoTilerMap\x12\x0c\n\x04rows\x18\x01 \x01(\x05\x12\x0c\n\x04\x63ols\x18\x02 \x01(\x05\x12+\n\x05tiles\x18\x03 \x03(\x0b\x32\x1c.autotiler.AutoTilerMap.Tile\x1a\xbb\x02\n\x04Tile\x12\x0b\n\x03row\x18\x01 \x01(\x05\x12\x0b\n\x03\x63ol\x18\x02 \x01(\x05\x12\x38\n\x0b\x62\x61seTerrain\x18\x03 \x01(\x0e\x32#.autotiler.AutoTilerMap.BaseTerrain\x12\x38\n\x0bimprovement\x18\x04 \x01(\x0e\x32#.autotiler.AutoTilerMap.Improvement\x12\x30\n\x07\x66\x65\x61ture\x18\x05 \x01(\x0e\x32\x1f.autotiler.AutoTilerMap.Feature\x12\x0c\n\x04\x66ood\x18\n \x01(\x05\x12\x12\n\nproduction\x18\x0b \x01(\x05\x12\x0c\n\x04gold\x18\x0c \x01(\x05\x12\x0f\n\x07science\x18\r \x01(\x05\x12\x0f\n\x07\x63ulture\x18\x0e \x01(\x05\x12\r\n\x05\x66\x61ith\x18\x0f \x01(\x05\x12\x12\n\nyieldValue\x18\x14 \x01(\x05\"\x95\x02\n\x0b\x42\x61seTerrain\x12\n\n\x06PLAINS\x10\x00\x12\r\n\tGRASSLAND\x10\x01\x12\n\n\x06\x44\x45SERT\x10\x02\x12\n\n\x06TUNDRA\x10\x03\x12\x08\n\x04SNOW\x10\x04\x12\t\n\x05\x43OAST\x10\x05\x12\t\n\x05OCEAN\x10\x06\x12\x10\n\x0cPLAINS_HILLS\x10\x07\x12\x13\n\x0fGRASSLAND_HILLS\x10\x08\x12\x10\n\x0c\x44\x45SERT_HILLS\x10\t\x12\x10\n\x0cTUNDRA_HILLS\x10\n\x12\x0e\n\nSNOW_HILLS\x10\x0b\x12\r\n\tMOUNTAINS\x10\x0c\x12\x19\n\x15GRASSLAND_FLOODPLAINS\x10\r\x12\x16\n\x12\x44\x45SERT_FLOODPLAINS\x10\x0e\x12\x16\n\x12PLAINS_FLOODPLAINS\x10\x0f\"p\n\x07\x46\x65\x61ture\x12\t\n\x05\x45MPTY\x10\x00\x12\t\n\x05WOODS\x10\x01\x12\x0e\n\nRAINFOREST\x10\x02\x12\t\n\x05MARSH\x10\x03\x12\t\n\x05OASIS\x10\x04\x12\x16\n\x12GEOTHERMAL_FISSURE\x10\x05\x12\x11\n\rVOLCANIC_SOIL\x10\x06\"!\n\x0bImprovement\x12\x08\n\x04NONE\x10\x00\x12\x08\n\x04\x43ITY\x10\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'protobuf.autotiler_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_AUTOTILERMAP']._serialized_start=40
  _globals['_AUTOTILERMAP']._serialized_end=874
  _globals['_AUTOTILERMAP_TILE']._serialized_start=130
  _globals['_AUTOTILERMAP_TILE']._serialized_end=445
  _globals['_AUTOTILERMAP_BASETERRAIN']._serialized_start=448
  _globals['_AUTOTILERMAP_BASETERRAIN']._serialized_end=725
  _globals['_AUTOTILERMAP_FEATURE']._serialized_start=727
  _globals['_AUTOTILERMAP_FEATURE']._serialized_end=839
  _globals['_AUTOTILERMAP_IMPROVEMENT']._serialized_start=841
  _globals['_AUTOTILERMAP_IMPROVEMENT']._serialized_end=874
# @@protoc_insertion_point(module_scope)
