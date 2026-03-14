import { useState, useEffect, useCallback, useMemo } from "react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { DeckGL } from "@deck.gl/react";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

const INITIAL_VIEW_STATE = {
  longitude: -16.55,
  latitude: 28.27,
  zoom: 9.5,
  pitch: 45,
  bearing: -15,
  maxZoom: 14,
  minZoom: 8,
};

// Dark basemap tiles (free, no API key)
const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

interface MunicipalityProperties {
  name: string;
  code: string;
  zone: string;
  tourism_intensity: number;
}

function intensityToColor(intensity: number): [number, number, number, number] {
  // Gradient from dark blue (low) → ocean blue → orange (high)
  if (intensity < 30) return [0, 30, 60, 160];
  if (intensity < 50) return [0, 80, 140, 180];
  if (intensity < 70) return [0, 135, 185, 200];
  if (intensity < 85) return [246, 155, 26, 200];
  return [255, 100, 20, 220];
}

interface TenerifeMapProps {
  className?: string;
  period?: string;
}

// Seasonal multiplier by month index (0=Jan..11=Dec), peak in Oct
const SEASONAL_FACTOR = [
  0.77, 0.75, 0.80, 0.82, 0.74, 0.75, 0.86, 0.84, 0.89, 1.0, 0.95, 0.91,
];

function getSeasonalMultiplier(period?: string): number {
  if (!period) return 1;
  const month = parseInt(period.split("-")[1], 10);
  if (isNaN(month) || month < 1 || month > 12) return 1;
  return SEASONAL_FACTOR[month - 1];
}

export default function TenerifeMap({ className = "", period }: TenerifeMapProps) {
  const [geojsonData, setGeojsonData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [hovered, setHovered] = useState<MunicipalityProperties | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const seasonalMult = useMemo(() => getSeasonalMultiplier(period), [period]);

  useEffect(() => {
    fetch("/tenerife.geojson")
      .then((r) => r.json())
      .then(setGeojsonData)
      .catch(console.error);
  }, []);

  const layers = geojsonData
    ? [
        new GeoJsonLayer({
          id: "municipalities",
          data: geojsonData,
          filled: true,
          stroked: true,
          extruded: true,
          updateTriggers: {
            getElevation: seasonalMult,
            getFillColor: seasonalMult,
          },
          getElevation: (f: GeoJSON.Feature) => {
            const base = (f.properties as MunicipalityProperties)?.tourism_intensity || 0;
            return Math.round(base * seasonalMult) * 50;
          },
          getFillColor: (f: GeoJSON.Feature) => {
            const base = (f.properties as MunicipalityProperties)?.tourism_intensity || 0;
            return intensityToColor(Math.round(base * seasonalMult));
          },
          getLineColor: [255, 255, 255, 40],
          getLineWidth: 1,
          lineWidthMinPixels: 1,
          pickable: true,
          autoHighlight: true,
          highlightColor: [0, 135, 185, 100],
          onHover: (info: { object?: GeoJSON.Feature; x?: number; y?: number }) => {
            if (info.object) {
              setHovered(info.object.properties as MunicipalityProperties);
              setTooltipPos({ x: info.x || 0, y: info.y || 0 });
            } else {
              setHovered(null);
            }
          },
        }),
      ]
    : [];

  const getTooltip = useCallback(() => {
    if (!hovered) return null;
    return null; // We render our own tooltip below
  }, [hovered]);

  return (
    <div className={`relative w-full h-full ${className}`}>
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller={true}
        layers={layers}
        getTooltip={getTooltip}
        style={{ position: "relative", width: "100%", height: "100%" }}
      >
        <Map mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Custom tooltip */}
      {hovered && (
        <div
          className="absolute pointer-events-none z-10 glass-panel px-3 py-2 text-sm"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 20,
          }}
        >
          <div className="font-semibold text-white">{hovered.name}</div>
          <div className="text-xs text-gray-400 mt-0.5">
            Zone: {hovered.zone}
          </div>
          <div className="text-xs text-ocean-400 mt-0.5">
            Tourism intensity: {hovered.tourism_intensity}%
          </div>
        </div>
      )}

      {/* Period indicator */}
      {period && (
        <div className="absolute top-3 right-3 glass-panel px-3 py-1.5">
          <span className="text-xs font-mono text-ocean-400">{period}</span>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 left-3 glass-panel px-3 py-2 text-[10px] space-y-1">
        <div className="text-gray-400 font-medium mb-1">Tourism Intensity</div>
        {[
          { label: "Very High", color: "bg-[#ff6414]" },
          { label: "High", color: "bg-[#f69b1a]" },
          { label: "Medium", color: "bg-[#0087b9]" },
          { label: "Low", color: "bg-[#00508c]" },
          { label: "Very Low", color: "bg-[#001e3c]" },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`w-3 h-2 rounded-sm ${color}`} />
            <span className="text-gray-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
