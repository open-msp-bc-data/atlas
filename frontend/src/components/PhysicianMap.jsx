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

// Simplified health authority boundary polygons (approximate)
const HA_BOUNDARIES = {
  'Interior Health': {
    color: '#B45309',
    coords: [
      [48.9, -121.0], [49.0, -119.0], [49.0, -115.5], [50.0, -114.7],
      [51.5, -116.5], [53.0, -119.5], [52.5, -121.5], [51.0, -122.0],
      [49.5, -121.5], [48.9, -121.0],
    ],
  },
  'Fraser Health': {
    color: '#2563EB',
    coords: [
      [48.9, -123.0], [49.0, -121.3], [49.5, -121.3], [49.5, -122.3],
      [49.4, -122.7], [49.35, -123.0], [48.9, -123.0],
    ],
  },
  'Vancouver Coastal Health': {
    color: '#1B7340',
    coords: [
      [49.0, -123.3], [49.35, -123.0], [49.4, -122.7], [49.5, -122.3],
      [50.5, -122.0], [51.5, -125.5], [50.5, -126.5], [49.3, -124.0],
      [49.0, -123.3],
    ],
  },
  'Island Health': {
    color: '#7C3AED',
    coords: [
      [48.3, -124.8], [48.4, -123.2], [49.0, -123.3], [49.3, -124.0],
      [50.5, -126.5], [50.8, -128.3], [50.0, -127.5], [49.0, -126.0],
      [48.3, -124.8],
    ],
  },
  'Northern Health': {
    color: '#DC2626',
    coords: [
      [51.5, -116.5], [53.0, -119.5], [52.5, -121.5], [51.0, -122.0],
      [51.5, -125.5], [50.8, -128.3], [54.0, -133.5], [60.0, -139.0],
      [60.0, -120.0], [56.0, -120.0], [54.0, -118.0], [51.5, -116.5],
    ],
  },
};

export default function PhysicianMap({
  physicians,
  heatmapData,
  showHeatmap,
  onSelectPhysician,
  onBoundsChange,
  selectedHealthAuthorities,
}) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef(null);
  const heatLayerRef = useRef(null);
  const haLayerRef = useRef(null);

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

    // Emit bounds on viewport change (debounced)
    let boundsTimer = null;
    function emitBounds() {
      clearTimeout(boundsTimer);
      boundsTimer = setTimeout(() => {
        if (!onBoundsChange) return;
        const b = map.getBounds();
        onBoundsChange({
          north: b.getNorth(),
          south: b.getSouth(),
          east: b.getEast(),
          west: b.getWest(),
        });
      }, 300);
    }
    map.on('moveend', emitBounds);
    emitBounds();

    return () => {
      clearTimeout(boundsTimer);
      map.off('moveend', emitBounds);
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

      // Color by specialty if known, otherwise by billing amount
      const color =
        phys.specialty_group && phys.specialty_group !== 'Unknown'
          ? SPECIALTY_COLORS[phys.specialty_group] || SPECIALTY_COLORS['Other Specialty']
          : billingColor(phys.latest_billing_range);

      const marker = L.marker([phys.lat_approx, phys.lng_approx], {
        icon: createCircleIcon(color),
      });

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

  // Update health authority boundary overlay
  useEffect(() => {
    const map = mapInstance.current;
    if (!map) return;

    if (haLayerRef.current) {
      map.removeLayer(haLayerRef.current);
      haLayerRef.current = null;
    }

    if (selectedHealthAuthorities && selectedHealthAuthorities.length > 0) {
      const group = L.layerGroup();
      selectedHealthAuthorities.forEach((ha) => {
        const boundary = HA_BOUNDARIES[ha];
        if (!boundary) return;
        const polygon = L.polygon(boundary.coords, {
          color: boundary.color,
          weight: 2,
          fillColor: boundary.color,
          fillOpacity: 0.08,
          dashArray: '6 4',
        });
        polygon.bindTooltip(ha, { sticky: true, className: 'physician-tooltip' });
        group.addLayer(polygon);
      });
      group.addTo(map);
      haLayerRef.current = group;
    }
  }, [selectedHealthAuthorities]);

  return <div ref={mapRef} className="map-container" />;
}
