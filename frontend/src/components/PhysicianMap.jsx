import { useEffect, useRef, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet.markercluster';

// Fix default Leaflet marker icon issue in bundled environments
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const BC_CENTER = [53.7, -127.6];
const BC_ZOOM = 5;

// Specialty → color mapping for markers
const SPECIALTY_COLORS = {
  'General Practice': '#4caf50',
  'Internal Medicine': '#2196f3',
  Surgery: '#f44336',
  Pediatrics: '#ff9800',
  Psychiatry: '#9c27b0',
  'Emergency Medicine': '#e91e63',
  Anesthesiology: '#00bcd4',
  Radiology: '#607d8b',
  'Obstetrics & Gynecology': '#ff5722',
  Dermatology: '#795548',
  Ophthalmology: '#3f51b5',
  Neurology: '#009688',
  Pathology: '#8bc34a',
  'Physical Medicine': '#cddc39',
  'Other Specialty': '#9e9e9e',
  Unknown: '#bdbdbd',
};

function createCircleIcon(color) {
  return L.divIcon({
    html: `<div style="
      background:${color};
      width:12px;height:12px;
      border-radius:50%;
      border:2px solid #fff;
      box-shadow:0 1px 3px rgba(0,0,0,0.3);
    "></div>`,
    className: '',
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

export default function PhysicianMap({
  physicians,
  heatmapData,
  showHeatmap,
  onSelectPhysician,
}) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef(null);
  const heatLayerRef = useRef(null);

  // Initialize map once
  useEffect(() => {
    if (mapInstance.current) return;

    const map = L.map(mapRef.current, {
      center: BC_CENTER,
      zoom: BC_ZOOM,
      zoomControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map);

    mapInstance.current = map;

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  // Update markers when physicians change
  useEffect(() => {
    const map = mapInstance.current;
    if (!map) return;

    // Remove old markers
    if (markersRef.current) {
      map.removeLayer(markersRef.current);
    }

    const cluster = L.markerClusterGroup({
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });

    physicians.forEach((phys) => {
      if (phys.lat_approx == null || phys.lng_approx == null) return;

      const color = SPECIALTY_COLORS[phys.specialty_group] || SPECIALTY_COLORS.Unknown;
      const marker = L.marker([phys.lat_approx, phys.lng_approx], {
        icon: createCircleIcon(color),
      });

      const tooltipContent = `
        <div class="physician-tooltip">
          <strong>${phys.pseudo_id}</strong><br/>
          Specialty: ${phys.specialty_group || 'Unknown'}<br/>
          City: ${phys.city || 'Unknown'}<br/>
          Billing: ${phys.latest_billing_range || 'N/A'}<br/>
          YoY Change: ${phys.yoy_change != null ? (phys.yoy_change * 100).toFixed(1) + '%' : 'N/A'}
        </div>
      `;

      marker.bindTooltip(tooltipContent, { sticky: true });
      marker.on('click', () => {
        if (onSelectPhysician) onSelectPhysician(phys.pseudo_id);
      });

      cluster.addLayer(marker);
    });

    map.addLayer(cluster);
    markersRef.current = cluster;
  }, [physicians, onSelectPhysician]);

  // Update heatmap layer
  useEffect(() => {
    const map = mapInstance.current;
    if (!map) return;

    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
    }

    if (showHeatmap && heatmapData.length > 0 && L.heatLayer) {
      const maxIntensity = Math.max(...heatmapData.map((p) => p.intensity));
      const points = heatmapData.map((p) => [
        p.lat,
        p.lng,
        p.intensity / maxIntensity,
      ]);

      const heat = L.heatLayer(points, {
        radius: 25,
        blur: 15,
        maxZoom: 12,
        gradient: { 0.2: '#ffffb2', 0.4: '#fecc5c', 0.6: '#fd8d3c', 0.8: '#f03b20', 1: '#bd0026' },
      });

      heat.addTo(map);
      heatLayerRef.current = heat;
    }
  }, [showHeatmap, heatmapData]);

  return <div ref={mapRef} className="map-container" style={{ height: '100%', minHeight: '400px' }} />;
}
