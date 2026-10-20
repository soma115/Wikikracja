const { spreadOverlappingMarkers } = require('../community-map');

describe('community map marker positioning', () => {
  const project = ([latitude, longitude]) => [longitude * 1000, latitude * 1000];
  const unproject = ([x, y]) => [y / 1000, x / 1000];

  test('keeps overlapping citizens, partners, and resources as separate markers', () => {
    const markers = [
      { type: 'citizen', latitude: 52, longitude: 21, items: [{ name: 'A' }] },
      { type: 'partner', latitude: 52, longitude: 21, items: [{ name: 'Partner' }] },
      { type: 'resource', latitude: 52, longitude: 21, items: [{ name: 'Drill' }] },
    ];

    const positioned = spreadOverlappingMarkers(markers, project, unproject);

    expect(positioned.map(({ marker }) => marker)).toEqual(markers);
    expect(positioned.map(({ marker }) => marker.type)).toEqual(['citizen', 'partner', 'resource']);
    expect(new Set(positioned.map(({ position }) => position.join(','))).size).toBe(3);
  });

  test('leaves non-overlapping marker locations unchanged', () => {
    const marker = { type: 'resource', latitude: 52, longitude: 21, items: [{ name: 'Drill' }] };

    expect(spreadOverlappingMarkers([marker], project, unproject)).toEqual([{ marker, position: [52, 21] }]);
  });

  test('starts over Poland and renders guest locations as non-interactive points', async () => {
    document.body.innerHTML = `
      <div id="community-map"
        data-map-data-url="/obywatele/mapa/data/"
        data-map-tiles-url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        data-map-member="false"
        data-map-error="Map data could not be loaded."></div>
      <div id="community-map-empty" class="tw-d-none"></div>
      <p id="community-map-status"></p>
    `;

    const map = { setView: jest.fn().mockReturnThis(), on: jest.fn() };
    const tileLayer = { addTo: jest.fn() };
    const layerGroup = { addTo: jest.fn().mockReturnThis(), clearLayers: jest.fn() };
    const pointMarker = { addTo: jest.fn() };
    const circleMarker = jest.fn(() => pointMarker);
    window.L = {
      map: jest.fn(() => map),
      tileLayer: jest.fn(() => tileLayer),
      layerGroup: jest.fn(() => layerGroup),
      circleMarker,
    };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ points: [{ lat: 52.1, lon: 19.4 }] }),
    });

    await window.WikikracjaCommunityMap.initializeMap();

    expect(map.setView).toHaveBeenCalledWith([52.1, 19.4], 6);
    expect(window.L.tileLayer).toHaveBeenCalledWith(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      expect.objectContaining({ referrerPolicy: 'origin' }),
    );
    expect(circleMarker).toHaveBeenCalledWith(
      [52.1, 19.4],
      expect.objectContaining({ interactive: false }),
    );
    expect(pointMarker.addTo).toHaveBeenCalledWith(layerGroup);
    expect(window.L.marker).toBeUndefined();
  });

  test('zooms to a member marker and shows its details in a safe popup', async () => {
    document.body.innerHTML = `
      <div id="community-map"
        data-map-data-url="/obywatele/mapa/data/"
        data-map-tiles-url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        data-map-member="true"
        data-map-error="Map data could not be loaded."
        data-map-citizen="Citizen"
        data-map-resource="Resource"
        data-map-details="Details"></div>
      <div id="community-map-empty" class="tw-d-none"></div>
      <section id="community-map-unmapped" class="tw-d-none"><h2></h2><div id="community-map-location-list"></div></section>
      <p id="community-map-status"></p>
    `;
    const clickHandlers = [];
    const marker = {
      bindPopup: jest.fn().mockReturnThis(),
      addTo: jest.fn().mockReturnThis(),
      on: jest.fn((event, handler) => clickHandlers.push(handler)),
    };
    const map = {
      setView: jest.fn().mockReturnThis(),
      on: jest.fn(),
      getZoom: jest.fn(() => 6),
      latLngToLayerPoint: ([latitude, longitude]) => ({ x: longitude * 1000, y: latitude * 1000 }),
      layerPointToLatLng: ([x, y]) => [y / 1000, x / 1000],
    };
    const layerGroup = { addTo: jest.fn().mockReturnThis(), clearLayers: jest.fn() };
    window.L = {
      map: jest.fn(() => map),
      tileLayer: jest.fn(() => ({ addTo: jest.fn() })),
      layerGroup: jest.fn(() => layerGroup),
      divIcon: jest.fn((options) => options),
      popup: jest.fn(() => ({ setContent: (content) => content })),
      marker: jest.fn(() => marker),
    };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        markers: [
          { type: 'citizen', latitude: 52.1, longitude: 19.4, items: [{ name: '<Jan>', address: 'Długa 4', url: '/obywatele/1/' }] },
          { type: 'resource', latitude: 50.1, longitude: 20.4, items: [{ name: 'Drill', address: 'Krakow', url: '/bookkeeping/resource/?q=Drill' }] },
          { type: 'partner', latitude: 53.1, longitude: 18.4, items: [{ name: 'Shop', address: 'Torun', url: '/bookkeeping/partner/1/' }] },
        ],
        unmapped: [],
      }),
    });

    await window.WikikracjaCommunityMap.initializeMap();

    expect(marker.bindPopup).toHaveBeenCalledTimes(3);
    const popup = marker.bindPopup.mock.calls[0][0];
    expect(popup.textContent).toContain('<Jan>');
    expect(popup.querySelector('script')).toBeNull();
    expect(marker.bindPopup.mock.calls[1][0].textContent).toContain('Resource');
    const markerIcons = window.L.divIcon.mock.calls.map(([options]) => options.html);
    expect(markerIcons[0]).toContain('tw-citizen-color-9');
    expect(markerIcons[0]).toContain('tw-text-white');
    expect(markerIcons[1]).toContain('tw-bg-[var(--color-success)]');
    expect(markerIcons[2]).toContain('tw-bg-warning');
    expect(markerIcons[1]).toContain('fa-boxes-stacked');
    clickHandlers[0]();
    expect(map.setView).toHaveBeenLastCalledWith([52.1, 19.4], 12, { animate: true });
  });
});
