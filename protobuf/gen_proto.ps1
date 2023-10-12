$scriptPath = Split-Path -parent $MyInvocation.MyCommand.Definition

# Go to the root of the project
cd $scriptPath/..

rm -r .\autotiler\lib\gen
mkdir .\autotiler\lib\gen
protoc .\protobuf\autotiler.proto --python_out backend --dart_out autotiler\lib\gen

Move-Item .\backend\protobuf\autotiler_pb2.py .\backend\autotiler_pb2.py -Force