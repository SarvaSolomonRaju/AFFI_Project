import { useEffect, useState } from "react";
import { Map, Source, Layer, Marker } from "react-map-gl/maplibre";
import type { StyleSpecification, ExpressionSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { apiGet, apiRasterUrl } from "../api/client";
import type { MapConfig } from "../types/api";

// A map library is different from a normal component: it draws
// straight onto a <canvas>, not into regular HTML, so React can't
// just re-render a <div> when data changes the way it does for a
// table. react-map-gl bridges that gap — you still write <Source>/
// <Layer> as JSX, and it translates that into MapLibre's own calls
// underneath. You get the React mental model back.

// No API key needed — plain OpenStreetMap raster tiles.
const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

// Same colors as style_zone() in src/dashboard/interactive_map.py —
// a MapLibre "match" expression is just an if/elif chain written as
// a JSON array instead of Python.
const NFHL_FILL_COLOR: ExpressionSpecification = [
  "match",
  ["get", "FLD_ZONE"],
  "AE", "#d73027",
  "A", "#fc8d59",
  "AO", "#fee090",
  "#cccccc",
];

export function FloodMap() {
  const [config, setConfig] = useState<MapConfig | null>(null);
  const [nfhlZones, setNfhlZones] = useState<GeoJSON.FeatureCollection | null>(null);
  const [roads, setRoads] = useState<GeoJSON.FeatureCollection | null>(null);
  const [buildings, setBuildings] = useState<GeoJSON.FeatureCollection | null>(null);

  useEffect(() => {
    apiGet<MapConfig>("/api/v1/map/config").then(setConfig);
    apiGet<GeoJSON.FeatureCollection>("/api/v1/map/layers/nfhl-zones").then(setNfhlZones);
    apiGet<GeoJSON.FeatureCollection>("/api/v1/map/layers/roads").then(setRoads);
    apiGet<GeoJSON.FeatureCollection>("/api/v1/map/layers/buildings").then(setBuildings);
  }, []);

  if (!config) return <p>Loading map…</p>;

  const b = config.raster_bounds["today-likely"];

  return (
    <div style={{ height: 520, marginTop: 20, borderRadius: 8, overflow: "hidden" }}>
      <Map
        mapStyle={BASE_STYLE}
        initialViewState={{
          longitude: config.center.lon,
          latitude: config.center.lat,
          zoom: 12,
          pitch: 45, // tilts the camera — this is what makes extruded buildings look 3D
        }}
      >
        {config.reference_markers.map((m) => (
          <Marker key={m.label} longitude={m.lon} latitude={m.lat}>
            <div title={m.label} style={{ fontSize: 20 }}>📍</div>
          </Marker>
        ))}

        {b && (
          <Source
            id="today-likely-raster"
            type="image"
            url={apiRasterUrl("/api/v1/map/raster/today-likely")}
            coordinates={[
              [b.west, b.north],
              [b.east, b.north],
              [b.east, b.south],
              [b.west, b.south],
            ]}
          >
            <Layer id="today-likely-layer" type="raster" paint={{ "raster-opacity": 0.75 }} />
          </Source>
        )}

        {nfhlZones && (
          <Source id="nfhl-zones" type="geojson" data={nfhlZones}>
            <Layer
              id="nfhl-zones-fill"
              type="fill"
              paint={{ "fill-color": NFHL_FILL_COLOR, "fill-opacity": 0.35 }}
            />
          </Source>
        )}

        {roads && (
          <Source id="roads" type="geojson" data={roads}>
            <Layer
              id="roads-line"
              type="line"
              paint={{
                "line-color": ["match", ["get", "status"], "FLOODED", "#d32f2f", "#37474f"],
                "line-width": ["match", ["get", "status"], "FLOODED", 3, 1.5],
              }}
            />
          </Source>
        )}

        {buildings && (
          <Source id="buildings" type="geojson" data={buildings}>
            {/* fill-extrusion is what gives buildings height/3D. We don't
                have real building-height data (see note below), so every
                building gets the same fixed height — the color is what
                carries the real signal (flooded vs safe). */}
            <Layer
              id="buildings-3d"
              type="fill-extrusion"
              paint={{
                "fill-extrusion-color": ["match", ["get", "status"], "FLOODED", "#e53935", "#78909c"],
                "fill-extrusion-height": 8,
                "fill-extrusion-opacity": 0.85,
              }}
            />
          </Source>
        )}
      </Map>
    </div>
  );
}
