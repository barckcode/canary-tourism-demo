import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { GeoJsonLayer } from "@deck.gl/layers";
import { DeckGL } from "@deck.gl/react";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMapData, MapMunicipality } from "../../api/hooks";
import { setupTooltipKeyboardDismiss } from "../../utils/chartAccessibility";
import ErrorState from "../shared/ErrorState";

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

interface HoveredMunicipality extends MunicipalityProperties {
  pernoctaciones?: number;
  source?: "real" | "estimated";
}

function intensityToColor(intensity: number): [number, number, number, number] {
  // Gradient from dark blue (low) -> ocean blue -> orange (high)
  if (intensity < 30) return [0, 30, 60, 160];
  if (intensity < 50) return [0, 80, 140, 180];
  if (intensity < 70) return [0, 135, 185, 200];
  if (intensity < 85) return [246, 155, 26, 200];
  return [255, 100, 20, 220];
}

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

interface TenerifeMapProps {
  className?: string;
  period?: string;
}

export default function TenerifeMap({ className = "", period }: TenerifeMapProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [geojsonData, setGeojsonData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [geojsonLoading, setGeojsonLoading] = useState(true);
  const [geojsonError, setGeojsonError] = useState(false);
  const [hovered, setHovered] = useState<HoveredMunicipality | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const { data: mapData } = useMapData(period);

  const apiMunicipalities = useMemo(() => {
    if (mapData?.data_available && mapData.municipalities) {
      return mapData.municipalities;
    }
    return null;
  }, [mapData]);

  const fetchGeojson = useCallback(() => {
    setGeojsonLoading(true);
    setGeojsonError(false);
    fetch("/tenerife.geojson")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setGeojsonData(data);
        setGeojsonLoading(false);
      })
      .catch(() => {
        setGeojsonError(true);
        setGeojsonLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchGeojson();
  }, [fetchGeojson]);

  // ESC key dismiss for keyboard accessibility (WCAG 1.4.13)
  useEffect(() => {
    return setupTooltipKeyboardDismiss(containerRef.current, () => setHovered(null));
  }, []);

  const getIntensity = useCallback(
    (f: GeoJSON.Feature): number => {
      const props = f.properties as MunicipalityProperties;
      if (apiMunicipalities && props.code && apiMunicipalities[props.code]) {
        return apiMunicipalities[props.code].tourism_intensity;
      }
      return props?.tourism_intensity || 0;
    },
    [apiMunicipalities]
  );

  const getApiData = useCallback(
    (code: string): MapMunicipality | null => {
      if (apiMunicipalities && code && apiMunicipalities[code]) {
        return apiMunicipalities[code];
      }
      return null;
    },
    [apiMunicipalities]
  );

  const layers = geojsonData
    ? [
        new GeoJsonLayer({
          id: "municipalities",
          data: geojsonData,
          filled: true,
          stroked: true,
          extruded: true,
          updateTriggers: {
            getElevation: apiMunicipalities,
            getFillColor: apiMunicipalities,
          },
          getElevation: (f: GeoJSON.Feature) => {
            return getIntensity(f) * 50;
          },
          getFillColor: (f: GeoJSON.Feature) => {
            return intensityToColor(getIntensity(f));
          },
          getLineColor: [255, 255, 255, 40],
          getLineWidth: 1,
          lineWidthMinPixels: 1,
          pickable: true,
          autoHighlight: true,
          highlightColor: [0, 135, 185, 100],
          onHover: (info: { object?: GeoJSON.Feature; x?: number; y?: number }) => {
            if (info.object) {
              const props = info.object.properties as MunicipalityProperties;
              const apiEntry = getApiData(props.code);
              const hoveredData: HoveredMunicipality = {
                ...props,
                tourism_intensity: apiEntry
                  ? apiEntry.tourism_intensity
                  : props.tourism_intensity,
                pernoctaciones: apiEntry?.pernoctaciones,
                source: apiEntry?.source,
              };
              setHovered(hoveredData);
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

  if (geojsonError) {
    return (
      <div className={`relative w-full h-full flex items-center justify-center ${className}`} role="region" aria-label="Interactive 3D map of Tenerife">
        <ErrorState message={t('common.errorLoading')} onRetry={fetchGeojson} />
      </div>
    );
  }

  if (geojsonLoading) {
    return (
      <div className={`relative w-full h-full flex items-center justify-center ${className}`} role="region" aria-label="Interactive 3D map of Tenerife">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-ocean-400 border-t-transparent rounded-full animate-spin" role="status" aria-label={t('common.loading')} />
          <span className="text-sm text-gray-400">{t('common.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`relative w-full h-full ${className}`} role="region" aria-label="Interactive 3D map of Tenerife showing tourism intensity by municipality. Use mouse or touch to pan, zoom, and rotate. Hover over municipalities for details." tabIndex={0}>
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
            {hovered.source === "estimated" && (
              <span className="text-gray-500 ml-1">(estimated)</span>
            )}
          </div>
          {hovered.pernoctaciones != null && (
            <div className="text-xs text-gray-300 mt-0.5">
              Overnight stays: {formatNumber(hovered.pernoctaciones)}
            </div>
          )}
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
            <span className="text-gray-400">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
