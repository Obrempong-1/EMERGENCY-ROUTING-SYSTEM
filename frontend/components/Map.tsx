"use client";

import { Fragment, useEffect, useRef, useState } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { AlertTriangle, Layers, Locate, Minus, Navigation, Phone, Plus, Radar } from 'lucide-react';

import type { CoverageResponse, Incident, MapMarker, RouteResponse, TransportMode } from '@/lib/api';
import { coverageColor, coverageWeight, type CoverageScope } from './map/coverage';
import CoverageKey from './map/CoverageKey';
import HelpButton from './map/HelpButton';
import MapLegend from './MapLegend';
import { styleFor } from './map/categories';
import { CategoryGlyph, IncidentGlyph } from './map/CategoryGlyph';
import { emergencyPin, facilityDot, incidentMarker, labelIcon, userPuck } from './map/markers';
import { useMapLabels } from './map/useMapLabels';
import { useIsDesktop } from '@/lib/useBreakpoint';
import MapTypeButton from './phone/MapTypeButton';
import ContactsButton from './phone/ContactsButton';

const CENTER: [number, number] = [6.6745, -1.5716];
const FALLBACK_BOUNDS: L.LatLngBoundsExpression = [[6.65, -1.60], [6.72, -1.52]];

const BASEMAPS = {
    satellite: {
        label: 'Satellite',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attribution: 'Tiles (c) Esri',
    },
    streets: {
        label: 'Streets',
        url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attribution: '(c) OpenStreetMap contributors',
    },
} as const;

type BasemapKey = keyof typeof BASEMAPS;

interface MapContentProps {
    locations: MapMarker[];
    activeLocation: { lat: number; lon: number } | null;
    activeId: string | null;
    onUserLocationUpdate?: (loc: { lat: number; lon: number }) => void;
    loadingRoute: boolean;
    requestNavigate: (destination: MapMarker) => void;
    routeData: RouteResponse | null;
    basemap: BasemapKey;
    coverage: CoverageResponse | null;
    onLongPress: (point: { lat: number; lon: number }) => void;
    incidents: Incident[];
    insetTop: number;
    insetBottom: number;
}

function MapContent({
    locations,
    activeLocation,
    activeId,
    onUserLocationUpdate,
    loadingRoute,
    requestNavigate,
    routeData,
    basemap,
    coverage,
    onLongPress,
    incidents,
    insetTop,
    insetBottom,
}: MapContentProps) {
    const map = useMap();

    const insets = useRef({ top: 0, bottom: 0 });
    useEffect(() => {
        insets.current = { top: insetTop, bottom: insetBottom };
    }, [insetTop, insetBottom]);

    useEffect(() => {
        if (!map) return;
        let timer: ReturnType<typeof setTimeout> | null = null;
        const cancel = () => { if (timer) { clearTimeout(timer); timer = null; } };
        const press = (event: L.LeafletMouseEvent) => {
            cancel();
            timer = setTimeout(() => {
                onLongPress({ lat: event.latlng.lat, lon: event.latlng.lng });
            }, 550);
        };
        const context = (event: L.LeafletMouseEvent) => {
            onLongPress({ lat: event.latlng.lat, lon: event.latlng.lng });
        };
        map.on('mousedown', press);
        map.on('mouseup', cancel);
        map.on('movestart', cancel);
        map.on('contextmenu', context);
        return () => {
            cancel();
            map.off('mousedown', press);
            map.off('mouseup', cancel);
            map.off('movestart', cancel);
            map.off('contextmenu', context);
        };
    }, [map, onLongPress]);

    const focusLat = activeLocation?.lat ?? null;
    const focusLon = activeLocation?.lon ?? null;
    useEffect(() => {
        if (!map || focusLat == null || focusLon == null) return;
        const zoom = Math.max(map.getZoom(), 17);
        const { top, bottom } = insets.current;
        const shifted = map.project([focusLat, focusLon], zoom)
            .add([0, (bottom - top) / 2]);
        map.flyTo(map.unproject(shifted, zoom), zoom, { animate: true, duration: 1.1 });
    }, [focusLat, focusLon, map]);

    const path = routeData?.path;
    useEffect(() => {
        if (map && path && path.length > 1) {
            const { top, bottom } = insets.current;
            map.fitBounds(L.latLngBounds(path as [number, number][]), {
                paddingTopLeft: [28, top + 56],
                paddingBottomRight: [28, bottom + 24],
                maxZoom: 18,
                animate: true,
            });
        }
    }, [map, path]);

    const placed = useMapLabels(map, locations, activeId);
    const tiles = BASEMAPS[basemap];

    return (
        <>
            <TileLayer
                key={basemap}
                url={tiles.url}
                attribution={tiles.attribution}
                maxNativeZoom={19}
                maxZoom={22}
            />

            {coverage?.bands.map((band) => (
                band.lines.length > 0 && (
                    <Polyline
                        key={`coverage-${band.index}`}
                        positions={band.lines}
                        pathOptions={{
                            color: coverageColor(band.index),
                            weight: coverageWeight(band.index),
                            opacity: 0.75,
                            lineCap: 'round',
                        }}
                    />
                )
            ))}

            {path && path.length > 1 && (
                <>
                    <Polyline positions={path} pathOptions={{
                        color: '#0b1220', weight: 11, opacity: 0.35,
                        lineCap: 'round', lineJoin: 'round',
                    }} />
                    <Polyline positions={path} pathOptions={{
                        color: '#22d3ee', weight: 6, opacity: 0.98,
                        lineCap: 'round', lineJoin: 'round',
                    }} />
                </>
            )}

            {placed.map(({ marker, showLabel, isEmergency }) => {
                const isUser = marker.category === 'user';
                const isActive = marker.id === activeId;
                const usesPin = isUser || isEmergency || isActive;

                let icon: L.DivIcon;
                if (isUser) icon = userPuck();
                else if (isEmergency || isActive) icon = emergencyPin(marker.category, isActive);
                else icon = facilityDot(isActive);

                return (
                    <Fragment key={marker.id}>
                        <Marker
                            position={[marker.lat, marker.lon]}
                            icon={icon}
                            zIndexOffset={isActive ? 1200 : isUser ? 1000 : isEmergency ? 500 : 0}
                            draggable={isUser}
                            eventHandlers={isUser ? {
                                dragend: (event) => {
                                    const { lat, lng } = (event.target as L.Marker).getLatLng();
                                    onUserLocationUpdate?.({ lat, lon: lng });
                                },
                            } : undefined}
                        >
                            {!isUser && (
                                <Popup className="knust-popup" closeButton={false} offset={[0, -4]}>
                                    <PlacePopup
                                        marker={marker}
                                        loading={loadingRoute}
                                        onNavigate={() => requestNavigate(marker)}
                                    />
                                </Popup>
                            )}
                        </Marker>

                        {showLabel && (
                            <Marker
                                position={[marker.lat, marker.lon]}
                                icon={labelIcon(marker.name, marker.category, usesPin ? 46 : 14)}
                                interactive={false}
                                zIndexOffset={isActive ? 1190 : isEmergency ? 490 : 0}
                            />
                        )}
                    </Fragment>
                );
            })}

            {incidents.map((incident) => (
                <Marker
                    key={`incident-${incident.id}`}
                    position={[incident.lat, incident.lon]}
                    icon={incidentMarker(incident.kind, incident.status, incident.confidence)}
                    zIndexOffset={1100}
                >
                    <Popup className="knust-popup" closeButton={false} offset={[0, -4]}>
                        <IncidentPopup incident={incident} />
                    </Popup>
                </Marker>
            ))}
        </>
    );
}

function IncidentPopup({ incident }: { incident: Incident }) {
    const minutesLeft = Number.isFinite(incident.expires_in_minutes)
        ? incident.expires_in_minutes
        : null;
    const hours = minutesLeft === null ? 0 : Math.floor(minutesLeft / 60);
    return (
        <div className="min-w-[188px] p-1">
            <div className="flex items-center gap-2">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-amber-50 text-amber-700">
                    <IncidentGlyph category={incident.kind} size={14} strokeWidth={2.3} />
                </span>
                <p className="text-[13.5px] font-semibold text-slate-900">{incident.label}</p>
            </div>
            <p className="mt-1.5 text-[11.5px] capitalize text-amber-700">
                {incident.status} &middot; {incident.reports} report
                {incident.reports === 1 ? '' : 's'}
            </p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div
                    className="h-full rounded-full bg-amber-500"
                    style={{ width: `${Math.round(incident.confidence * 100)}%` }}
                />
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">
                {Math.round(incident.confidence * 100)}% confidence
                {minutesLeft === null
                    ? ''
                    : ` · clears in ${hours >= 1 ? `${hours}h` : `${minutesLeft}m`}`}
            </p>
        </div>
    );
}

function PlacePopup({ marker, loading, onNavigate }: {
    marker: MapMarker;
    loading: boolean;
    onNavigate: () => void;
}) {
    const style = styleFor(marker.category);
    return (
        <div className="w-[248px] p-1">
            <div className="flex items-start gap-3">
                <span
                    className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl text-white"
                    style={{ background: style.color }}
                >
                    <CategoryGlyph category={marker.category} size={17} strokeWidth={2.2} />
                </span>
                <div className="min-w-0">
                    <h3 className="truncate text-[15px] font-semibold leading-tight text-slate-900">
                        {marker.name}
                    </h3>
                    <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                        {marker.category === 'facility'
                            ? marker.type.replace(/_/g, ' ')
                            : style.label}
                    </p>
                </div>
            </div>

            {(marker.opening_hours || marker.phone) && (
                <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
                    {marker.opening_hours && (
                        <p className="text-[12px] text-slate-600">{marker.opening_hours}</p>
                    )}
                    {marker.phone && (
                        <a
                            href={`tel:${marker.phone}`}
                            className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-blue-600"
                        >
                            <Phone size={13} /> {marker.phone}
                        </a>
                    )}
                </div>
            )}

            <button
                onClick={onNavigate}
                disabled={loading}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 px-3 py-2.5 text-[13px] font-semibold text-white transition active:scale-[.98] disabled:opacity-60"
            >
                <Navigation size={15} />
                {loading ? 'Calculating...' : 'Directions'}
            </button>
        </div>
    );
}

interface MapComponentProps {
    locations: MapMarker[];
    activeLocation: { lat: number; lon: number } | null;
    activeId: string | null;
    routeData: RouteResponse | null;
    loadingRoute: boolean;
    serviceBounds: { min_lat: number; max_lat: number; min_lon: number; max_lon: number } | null;
    onUserLocationUpdate?: (loc: { lat: number; lon: number }) => void;
    onNavigate: (start: { lat: number; lon: number }, destination: MapMarker) => void;
    onRouteError: (message: string) => void;
    onLocateMe: () => void;
    coverage: CoverageResponse | null;
    coverageLoading: boolean;
    onToggleCoverage: () => void;
    coverageScope: CoverageScope;
    onCoverageScopeChange: (scope: CoverageScope) => void;
    coverageMode: TransportMode;
    onCoverageModeChange: (mode: TransportMode) => void;
    onLongPress: (point: { lat: number; lon: number }) => void;
    incidents: Incident[];
    onReportIncident: () => void;
    topBarBottom: number;
    sheetBottom: number;
    onContactsOpen?: () => void;
}

export default function MapComponent({
    locations,
    activeLocation,
    activeId,
    routeData,
    loadingRoute,
    serviceBounds,
    onUserLocationUpdate,
    onNavigate,
    onRouteError,
    onLocateMe,
    coverage,
    coverageLoading,
    onToggleCoverage,
    coverageScope,
    onCoverageScopeChange,
    coverageMode,
    onCoverageModeChange,
    onLongPress,
    incidents,
    onReportIncident,
    topBarBottom,
    sheetBottom,
    onContactsOpen,
}: MapComponentProps) {
    const [map, setMap] = useState<L.Map | null>(null);
    const [basemap, setBasemap] = useState<BasemapKey>('satellite');
    const isDesktop = useIsDesktop();

    useEffect(() => {
        if (!map) return;
        const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }));
        observer.observe(map.getContainer());
        return () => observer.disconnect();
    }, [map]);

    const userLocation = locations.find((l) => l.category === 'user');

    const requestNavigate = async (destination: MapMarker) => {
        let startLat = userLocation?.lat;
        let startLon = userLocation?.lon;

        if (startLat == null || startLon == null) {
            try {
                const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, {
                        enableHighAccuracy: true, timeout: 10000, maximumAge: 0,
                    });
                });
                startLat = pos.coords.latitude;
                startLon = pos.coords.longitude;
                onUserLocationUpdate?.({ lat: startLat, lon: startLon });
            } catch {
                onRouteError('Could not detect your location. Enable location access to use Directions.');
                return;
            }
        }

        if (serviceBounds) {
            const outside =
                startLat < serviceBounds.min_lat || startLat > serviceBounds.max_lat ||
                startLon < serviceBounds.min_lon || startLon > serviceBounds.max_lon;
            if (outside) {
                onRouteError('You appear to be outside the mapped KNUST area, so routing from your position is unavailable.');
                return;
            }
        }

        onNavigate({ lat: startLat, lon: startLon }, destination);
    };

    const bounds: L.LatLngBoundsExpression = serviceBounds
        ? [[serviceBounds.min_lat, serviceBounds.min_lon],
           [serviceBounds.max_lat, serviceBounds.max_lon]]
        : FALLBACK_BOUNDS;

    return (
        <div className="relative h-full w-full">
            <MapContainer
                ref={setMap}
                center={CENTER}
                zoom={16}
                minZoom={14}
                maxZoom={22}
                maxBounds={bounds}
                maxBoundsViscosity={1}
                style={{ height: '100%', width: '100%', zIndex: 0 }}
                zoomControl={false}
                attributionControl={false}
                zoomSnap={0}
                zoomDelta={0.3}
                wheelPxPerZoomLevel={70}
            >
                <MapContent
                    locations={locations}
                    activeLocation={activeLocation}
                    activeId={activeId}
                    onUserLocationUpdate={onUserLocationUpdate}
                    loadingRoute={loadingRoute}
                    requestNavigate={requestNavigate}
                    routeData={routeData}
                    basemap={basemap}
                    coverage={coverage}
                    onLongPress={onLongPress}
                    incidents={incidents}
                    insetTop={topBarBottom}
                    insetBottom={sheetBottom}
                />
            </MapContainer>

            <div className="absolute right-4 top-4 z-[690] hidden w-[9.5rem] flex-col gap-2 lg:flex">
                <div className="relative z-10 flex h-10 w-full items-center rounded-full bg-white/95 text-slate-700 shadow-lg ring-1 ring-black/5 backdrop-blur">
                    <button
                        onClick={() => setBasemap((b) => (b === 'satellite' ? 'streets' : 'satellite'))}
                        aria-label={`Switch to ${basemap === 'satellite' ? 'street' : 'satellite'} map`}
                        className="flex h-full flex-1 items-center justify-center gap-2 rounded-l-full pl-3 text-[12px] font-semibold transition active:scale-95"
                    >
                        <Layers size={15} />
                        <span>{BASEMAPS[basemap].label}</span>
                    </button>
                    <span aria-hidden className="h-5 w-px bg-slate-200" />
                    <HelpButton id="basemap-help" label="What is this map view?" title="Map view">
                        <p>Tap to switch the background between two views.</p>
                        <p>
                            <span className="font-semibold text-slate-800">Satellite</span> shows real
                            aerial photos, so you can spot buildings, fields and landmarks you recognise.
                        </p>
                        <p>
                            <span className="font-semibold text-slate-800">Streets</span> shows a clean
                            drawn map with road and place names, which is easier for following a route.
                        </p>
                        <p className="text-slate-500">
                            Only the background changes. Routes, places and coverage stay the same.
                        </p>
                    </HelpButton>
                </div>

                <div
                    className={`flex h-10 w-full items-center rounded-full shadow-lg ring-1 ring-black/5 backdrop-blur transition ${
                        coverage ? 'bg-slate-900 text-white' : 'bg-white/95 text-slate-700'
                    }`}
                >
                    <button
                        onClick={onToggleCoverage}
                        aria-pressed={coverage !== null}
                        aria-label="Toggle response coverage"
                        className="flex h-full flex-1 items-center justify-center gap-2 rounded-l-full pl-3 text-[12px] font-semibold transition active:scale-95"
                    >
                        <Radar size={15} className={coverageLoading ? 'animate-spin' : ''} />
                        <span>Coverage</span>
                    </button>
                    <span aria-hidden className={`h-5 w-px ${coverage ? 'bg-white/25' : 'bg-slate-200'}`} />
                    <HelpButton
                        id="coverage-help"
                        label="What is coverage?"
                        title="What is Coverage?"
                        active={coverage !== null}
                    >
                        <p>
                            It colours every road by how long help would take to reach it from the
                            nearest emergency facility, so you can see which areas are well served
                            and which are far from help.
                        </p>
                        <ul className="space-y-1 text-[11px]">
                            <li><span className="font-semibold text-green-600">Green</span> means help arrives fast.</li>
                            <li><span className="font-semibold text-red-600">Red</span> means a long wait.</li>
                            <li><span className="font-semibold text-fuchsia-700">Purple</span> means over 15 min or no road access.</li>
                        </ul>
                        <p className="text-[11px] text-slate-500">
                            Choose All, Medical, Police or Fire to see one service at a time.
                            Travel mode and traffic from the sidebar change the result.
                        </p>
                    </HelpButton>
                </div>
            </div>

            <div
                className="absolute right-3 z-[600] flex flex-col gap-2 sm:right-4 lg:bottom-8"
                style={{ bottom: isDesktop ? undefined : sheetBottom + 12 }}
            >
                <button
                    onClick={onReportIncident}
                    aria-label="Report an incident"
                    className="grid h-11 w-11 place-items-center rounded-full bg-amber-500 text-white shadow-lg ring-1 ring-black/5 transition active:scale-95"
                >
                    <AlertTriangle size={18} />
                </button>
                <button
                    onClick={onLocateMe}
                    aria-label="Centre on my location"
                    className="grid h-11 w-11 place-items-center rounded-full bg-white/95 text-slate-700 shadow-lg ring-1 ring-black/5 backdrop-blur transition active:scale-95"
                >
                    <Locate size={18} />
                </button>
                <div className="hidden flex-col overflow-hidden rounded-full bg-white/95 shadow-lg ring-1 ring-black/5 backdrop-blur lg:flex">
                    <button onClick={() => map?.zoomIn()} aria-label="Zoom in"
                        className="grid h-11 w-11 place-items-center text-slate-700 transition active:scale-95">
                        <Plus size={18} />
                    </button>
                    <span className="mx-auto h-px w-5 bg-slate-200" />
                    <button onClick={() => map?.zoomOut()} aria-label="Zoom out"
                        className="grid h-11 w-11 place-items-center text-slate-700 transition active:scale-95">
                        <Minus size={18} />
                    </button>
                </div>
            </div>

            <div
                className="absolute left-3 z-[600] flex flex-col items-start gap-2 lg:bottom-6 lg:left-4"
                style={{ bottom: isDesktop ? undefined : sheetBottom + 12 }}
            >
                <div
                    aria-hidden={coverage !== null}
                    className={`hidden origin-bottom-left lg:block motion-safe:transition-[filter,opacity,transform] motion-safe:duration-300 motion-safe:ease-out ${
                        coverage ? 'pointer-events-none -translate-y-12 scale-[0.94] opacity-70 blur-[1.5px] saturate-50' : ''
                    }`}
                >
                    <MapLegend />
                </div>
                <CoverageKey
                    mode={coverageMode}
                    onModeChange={onCoverageModeChange}
                    coverage={coverage}
                    loading={coverageLoading}
                    scope={coverageScope}
                    onScopeChange={onCoverageScopeChange}
                />
                <ContactsButton onOpen={onContactsOpen} />
                <MapTypeButton
                    map={map}
                    label={BASEMAPS[basemap === 'satellite' ? 'streets' : 'satellite'].label}
                    tileUrl={BASEMAPS[basemap === 'satellite' ? 'streets' : 'satellite'].url}
                    maxNativeZoom={19}
                    onToggle={() => setBasemap((b) => (b === 'satellite' ? 'streets' : 'satellite'))}
                />
            </div>

            <p
                className="absolute bottom-0 left-0 z-[600] bg-white/70 px-2 py-0.5 text-[9px] text-slate-500 backdrop-blur-sm lg:left-0 lg:translate-x-0"
                style={isDesktop ? undefined : {
                    bottom: sheetBottom,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    borderRadius: '6px 6px 0 0',
                }}
            >
                {BASEMAPS[basemap].attribution} &middot; Leaflet
            </p>
        </div>
    );
}
