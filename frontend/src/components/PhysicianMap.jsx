import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet.markercluster';
import 'leaflet.heat';

// Fix default Leaflet marker icon issue in bundled environments
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const BC_CENTER = [53.7, -127.6];
const BC_ZOOM = 5;

// Jitter radius in km (must match backend privacy.location_jitter_km)
const JITTER_RADIUS_KM = 1.5;

// Specialty → color mapping for markers
const SPECIALTY_COLORS = {
  'General Practice': '#1B7340',
  'Internal Medicine': '#2563EB',
  Surgery: '#C4122F',
  Pediatrics: '#B45309',
  Psychiatry: '#7C3AED',
  'Emergency Medicine': '#DC2626',
  Anesthesiology: '#0891B2',
  Radiology: '#6B7280',
  'Obstetrics & Gynecology': '#BE185D',
  Dermatology: '#92400E',
  Ophthalmology: '#1D4ED8',
  Neurology: '#0F766E',
  Pathology: '#4D7C0F',
  'Physical Medicine': '#A16207',
  'Other Specialty': '#9CA3AF',
  Unknown: '#9CA3AF',
};

// Billing amount → color (used when specialty is unknown)
function billingColor(rangeStr) {
  if (!rangeStr) return '#D1D1CC';
  const match = rangeStr.match(/(\d+)k/);
  if (!match) return '#D1D1CC';
  const lower = parseInt(match[1], 10);
  if (lower >= 500) return '#5C0816';
  if (lower >= 300) return '#C4122F';
  if (lower >= 200) return '#E86060';
  if (lower >= 100) return '#F5A3A3';
  return '#FDE8E8';
}

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
  const jitterCirclesRef = useRef(null);

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

    // Remove old markers and jitter circles
    if (markersRef.current) {
      map.removeLayer(markersRef.current);
    }
    if (jitterCirclesRef.current) {
      map.removeLayer(jitterCirclesRef.current);
    }

    const cluster = L.markerClusterGroup({
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });

    const jitterGroup = L.layerGroup();

    physicians.forEach((phys) => {
      if (phys.lat_approx == null || phys.lng_approx == null) return;

      // Color by specialty if known, otherwise by billing amount
      const color =
        phys.specialty_group && phys.specialty_group !== 'Unknown'
          ? SPECIALTY_COLORS[phys.specialty_group] || SPECIALTY_COLORS['Other Specialty']
          : billingColor(phys.latest_billing_range);

      const marker = L.marker([phys.lat_approx, phys.lng_approx], {
        icon: createCircleIcon(color),
      });

      // Jitter radius circle (shows approximate area, visible on zoom)
      const circle = L.circle([phys.lat_approx, phys.lng_approx], {
        radius: JITTER_RADIUS_KM * 1000,
        color: '#C4122F',
        fillColor: '#C4122F',
        fillOpacity: 0.04,
        weight: 0.5,
        opacity: 0.15,
        interactive: false,
      });
      jitterGroup.addLayer(circle);

      const tooltipEl = document.createElement('div');
      tooltipEl.className = 'physician-tooltip';

      const idEl = document.createElement('strong');
      idEl.textContent = phys.pseudo_id;
      tooltipEl.appendChild(idEl);
      tooltipEl.appendChild(document.createElement('br'));

      tooltipEl.appendChild(document.createTextNode(`Specialty: ${phys.specialty_group || 'Unknown'}`));
      tooltipEl.appendChild(document.createElement('br'));
      tooltipEl.appendChild(document.createTextNode(`City: ${phys.city || 'Unknown'}`));
      tooltipEl.appendChild(document.createElement('br'));
      tooltipEl.appendChild(document.createTextNode(`Billing: ${phys.latest_billing_range || 'N/A'}`));
      tooltipEl.appendChild(document.createElement('br'));
      tooltipEl.appendChild(
        document.createTextNode(
          `YoY Change: ${phys.yoy_change != null ? (phys.yoy_change * 100).toFixed(1) + '%' : 'N/A'}`
        )
      );

      marker.bindTooltip(tooltipEl, { sticky: true });
      marker.on('click', () => {
        if (onSelectPhysician) onSelectPhysician(phys.pseudo_id);
      });

      cluster.addLayer(marker);
    });

    map.addLayer(jitterGroup);
    map.addLayer(cluster);
    markersRef.current = cluster;
    jitterCirclesRef.current = jitterGroup;
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
      const maxIntensity = Math.max(...heatmapData.map((p) => p.intensity), 1);
      const points = heatmapData.map((p) => [
        p.lat,
        p.lng,
        p.intensity / maxIntensity,
      ]);

      const heat = L.heatLayer(points, {
        radius: 40,
        blur: 25,
        maxZoom: 10,
        gradient: { 0.2: '#FDE8E8', 0.4: '#F5A3A3', 0.6: '#E86060', 0.8: '#C4122F', 1: '#5C0816' },
      });

      heat.addTo(map);
      heatLayerRef.current = heat;
    }
  }, [showHeatmap, heatmapData]);

  return <div ref={mapRef} className="map-container" style={{ height: '100%', minHeight: '400px' }} />;
}
