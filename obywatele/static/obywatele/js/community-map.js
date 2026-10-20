(function (root, createApi) {
  const api = createApi();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.WikikracjaCommunityMap = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const ICONS = {
    citizen: 'fa-user',
    partner: 'fa-handshake',
    resource: 'fa-boxes-stacked',
  };
  const MARKER_STYLES = {
    citizen: 'tw-citizen-color-9 tw-text-white',
    partner: 'tw-bg-warning tw-text-gray-900',
    resource: 'tw-bg-[var(--color-success)] tw-text-gray-900',
  };
  const INITIAL_CENTER = [52.1, 19.4];
  const INITIAL_ZOOM = 6;

  function projectPoint(point) {
    return Array.isArray(point) ? point : [point.x, point.y];
  }

  function spreadOverlappingMarkers(markers, project, unproject, radius = 32) {
    const groups = [];
    for (const marker of markers) {
      const projected = projectPoint(project([marker.latitude, marker.longitude]));
      const entry = { marker, projected };
      const matches = groups.filter((group) => group.some((candidate) => Math.hypot(candidate.projected[0] - projected[0], candidate.projected[1] - projected[1]) <= radius));

      if (!matches.length) {
        groups.push([entry]);
        continue;
      }

      matches[0].push(entry);
      for (const duplicate of matches.slice(1)) {
        matches[0].push(...duplicate);
        groups.splice(groups.indexOf(duplicate), 1);
      }
    }

    return groups.flatMap((group) => {
      if (group.length === 1) {
        const { marker } = group[0];
        return [{ marker, position: [marker.latitude, marker.longitude] }];
      }

      const center = group.reduce(
        (point, entry) => [point[0] + entry.projected[0] / group.length, point[1] + entry.projected[1] / group.length],
        [0, 0],
      );
      const offsetRadius = (radius + 4) / (2 * Math.sin(Math.PI / group.length));
      return group.map(({ marker }, index) => {
        const angle = -Math.PI / 2 + (index * 2 * Math.PI) / group.length;
        const point = [center[0] + Math.cos(angle) * offsetRadius, center[1] + Math.sin(angle) * offsetRadius];
        return { marker, position: unproject(point) };
      });
    });
  }

  function createMarkerIcon(leaflet, type) {
    const marker = document.createElement('span');
    marker.className = `tw-w-8 tw-h-8 tw-rounded-full ${MARKER_STYLES[type] || 'tw-bg-info tw-text-gray-900'} tw-flex tw-items-center tw-justify-center tw-border-2 tw-border-white tw-shadow-lg`;
    const icon = document.createElement('i');
    icon.className = `fas ${ICONS[type] || 'fa-map-marker-alt'} fa-fw`;
    icon.setAttribute('aria-hidden', 'true');
    marker.appendChild(icon);
    return leaflet.divIcon({
      html: marker.outerHTML,
      className: '',
      iconSize: [32, 32],
      iconAnchor: [16, 16],
      popupAnchor: [0, -16],
    });
  }

  function makePopup(leaflet, entries, root) {
    const content = document.createElement('div');
    content.className = 'tw-flex tw-flex-col tw-gap-2';
    for (const entry of entries) {
      const item = document.createElement('div');
      item.className = 'tw-flex tw-flex-col tw-gap-1';

      if (entry.type) {
        const typeLabel = document.createElement('span');
        typeLabel.className = 'tw-text-xs tw-text-muted';
        const labelKey = `map${entry.type.replace(/(^|_)([a-z])/g, (_, __, letter) => letter.toUpperCase())}`;
        typeLabel.textContent = root.dataset[labelKey] || '';
        item.appendChild(typeLabel);
      }

      const name = document.createElement('strong');
      name.textContent = entry.name || '';
      item.appendChild(name);

      if (entry.address) {
        const address = document.createElement('span');
        address.textContent = entry.address;
        item.appendChild(address);
      }

      if (entry.url) {
        const link = document.createElement('a');
        link.href = entry.url;
        link.textContent = document.getElementById('community-map').dataset.mapDetails;
        item.appendChild(link);
      }
      content.appendChild(item);
    }
    return leaflet.popup().setContent(content);
  }

  function detailRecords(data) {
    return [
      ...(data.markers || []).flatMap((marker) => (marker.items || []).map((item) => ({ ...item, type: marker.type }))),
      ...(data.unmapped || []).map((item) => ({ ...item, unmapped: true })),
    ];
  }

  function renderDetailsList(records, root, { allRecords = false } = {}) {
    const panel = document.getElementById('community-map-unmapped');
    const list = document.getElementById('community-map-location-list');
    if (!panel || !list) return;

    const visibleRecords = allRecords ? records : records.filter((record) => !record.url || record.unmapped);
    list.replaceChildren();
    for (const record of visibleRecords) {
      const card = document.createElement('div');
      card.className = 'tw-card tw-p-3 tw-flex tw-flex-col tw-gap-1';
      const label = document.createElement('span');
      label.className = 'tw-text-xs tw-text-muted';
      label.textContent = root.dataset[`map${record.type.replace(/(^|_)([a-z])/g, (_, __, letter) => letter.toUpperCase())}`] || '';
      card.appendChild(label);

      const name = document.createElement('strong');
      name.textContent = record.name || '';
      card.appendChild(name);

      if (record.address) {
        const address = document.createElement('span');
        address.textContent = record.address;
        card.appendChild(address);
      }

      if (record.url) {
        const link = document.createElement('a');
        link.href = record.url;
        link.textContent = root.dataset.mapDetails;
        card.appendChild(link);
      }
      list.appendChild(card);
    }
    panel.classList.toggle('tw-d-none', visibleRecords.length === 0);
    panel.querySelector('h2').textContent = root.dataset.mapUnmappedTitle;
  }

  function initializeMap() {
    const root = document.getElementById('community-map');
    if (!root) return;

    const status = document.getElementById('community-map-status');
    const empty = document.getElementById('community-map-empty');
    const showDetails = root.dataset.mapMember === 'true';
    const reportError = () => {
      status.textContent = root.dataset.mapError;
      status.classList.remove('tw-d-none');
    };

    return fetch(root.dataset.mapDataUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((response) => {
        if (!response.ok) throw new Error('Map data request failed');
        return response.json();
      })
      .then((data) => {
        const records = showDetails ? detailRecords(data) : [];
        if (showDetails) renderDetailsList(records, root);

        const leaflet = window.L;
        if (!leaflet) {
          reportError();
          if (showDetails) renderDetailsList(records, root, { allRecords: true });
          empty.classList.toggle('tw-d-none', records.length > 0);
          return;
        }

        const map = leaflet.map(root, { scrollWheelZoom: false }).setView(INITIAL_CENTER, INITIAL_ZOOM);
        leaflet.tileLayer(root.dataset.mapTilesUrl, {
          maxZoom: 19,
          noWrap: true,
          keepBuffer: 0,
          updateWhenIdle: true,
          updateInterval: 1000,
          referrerPolicy: 'origin',
          attribution: root.dataset.mapTilesAttribution,
        }).addTo(map);
        const markersLayer = leaflet.layerGroup().addTo(map);

        if (showDetails) {
          const markers = data.markers || [];
          const drawMarkers = () => {
            markersLayer.clearLayers();
            const positionedMarkers = spreadOverlappingMarkers(
              markers,
              (coordinates) => map.latLngToLayerPoint(coordinates),
              (point) => map.layerPointToLatLng(point),
            );
            for (const { marker: mapMarker, position } of positionedMarkers) {
              const entries = (mapMarker.items || []).map((item) => ({ ...item, type: mapMarker.type }));
              const marker = leaflet.marker(position, { icon: createMarkerIcon(leaflet, mapMarker.type) })
                .bindPopup(makePopup(leaflet, entries, root))
                .addTo(markersLayer);
              marker.on('click', () => map.setView(position, Math.max(map.getZoom(), 12), { animate: true }));
            }
          };
          drawMarkers();
          map.on('zoomend', drawMarkers);
          map.on('tileerror', () => {
            reportError();
            renderDetailsList(records, root, { allRecords: true });
          });
          empty.classList.toggle('tw-d-none', markers.length + (data.unmapped || []).length > 0);
        } else {
          const points = data.points || [];
          for (const point of points) {
            leaflet.circleMarker([point.lat, point.lon], {
              radius: 5,
              color: '#ffffff',
              weight: 1,
              fillColor: '#3976c5',
              fillOpacity: 0.85,
              interactive: false,
            }).addTo(markersLayer);
          }
          empty.classList.toggle('tw-d-none', points.length > 0);
        }
      })
      .catch(() => {
        reportError();
        if (empty) empty.classList.remove('tw-d-none');
      });
  }

  return { spreadOverlappingMarkers, initializeMap };
});

if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => window.WikikracjaCommunityMap?.initializeMap());
}
