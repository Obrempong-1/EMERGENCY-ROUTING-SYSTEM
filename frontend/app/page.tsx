"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
    ChevronLeft,
    ChevronRight,
    MapPin,
    MapPinPlus,
    PanelLeftOpen,
    Radar,
    Route,
    Search,
    ShieldAlert,
    ShieldCheck,
    SlidersHorizontal,
    TriangleAlert,
} from "lucide-react";

import {
    errorMessage,
    EmergencyCategory,
    MapMarker,
    TrafficLevel,
    TransportMode,
} from "../lib/api";
import {
    useBounds,
    useCategories,
    useCoverage,
    useIncidents,
    useLocations,
    useModeEtas,
    useSession,
} from "../lib/queries";
import { useRouting } from "../lib/useRouting";
import { useUserLocation } from "../lib/useUserLocation";
import SidebarHeader from "../components/sidebar/SidebarHeader";
import { RouteStops } from "../components/sidebar/RouteConfig";
import PlacePicker from "../components/sidebar/PlacePicker";
import CreatorFooter from "../components/sidebar/CreatorFooter";
import BottomSheet, { type SheetSnap } from "../components/BottomSheet";
import EmergencyPicker from "../components/sidebar/EmergencyPicker";
import PinPlaceDialog from "../components/PinPlaceDialog";
import EmergencyBar from "../components/EmergencyBar";
import ModeTabs, { type PanelMode } from "../components/sidebar/ModeTabs";
import ReportIncidentDialog from "../components/ReportIncidentDialog";
import TopBar from "../components/TopBar";
import RouteAnalysis from "../components/RouteAnalysis";
import EmergencyFlow from "../components/phone/EmergencyFlow";
import NearestList from "../components/phone/NearestList";
import MoreSheet, { type MoreRow } from "../components/phone/MoreSheet";
import { RouteSummary } from "../components/phone/RouteSummary";
import { useIsDesktop } from "../lib/useBreakpoint";
import { can } from "../lib/roles";
import RoleIntroCard from "../components/RoleIntroCard";
import { metresBetween } from "../lib/geo";
import { styleFor } from "../components/map/categories";
import { scopeCategories, type CoverageScope } from "../components/map/coverage";

const MapComponent = dynamic(() => import("../components/Map"), { ssr: false });

const CURRENT_LOCATION = "__current_location__";

type PhoneView = "home" | "more" | "search" | "directions";

const REROUTE_THRESHOLD_M = 20;

export default function Home() {
    const locationsQuery = useLocations();
    const boundsQuery = useBounds();
    const categoriesQuery = useCategories();

    const locations = useMemo(() => locationsQuery.data ?? [], [locationsQuery.data]);
    const bounds = boundsQuery.data ?? null;
    const categories = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);
    const locationsLoading = locationsQuery.isPending;
    const locationsError = locationsQuery.isError
        ? errorMessage(locationsQuery.error, "Could not load campus facilities.")
        : "";

    const isDesktop = useIsDesktop();

    const [transportMode, setTransportMode] = useState<TransportMode>("drive");
    const [trafficLevel, setTrafficLevel] = useState<TrafficLevel>("normal");

    const traffic: TrafficLevel = transportMode === "drive" ? trafficLevel : "normal";

    const routing = useRouting(transportMode, traffic);
    const gps = useUserLocation(bounds, !isDesktop);

    const [originId, setOriginId] = useState<string>("");
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [panelMode, setPanelMode] = useState<PanelMode>("emergency");

    const [emergencyCategory, setEmergencyCategory] = useState<EmergencyCategory | null>(null);
    const [emergencySubtype, setEmergencySubtype] = useState<string | null>(null);

    const [coverageOn, setCoverageOn] = useState(false);
    const [coverageScope, setCoverageScope] = useState<CoverageScope>("all");
    const [coverageMode, setCoverageMode] = useState<TransportMode>("drive");

    const [centreOn, setCentreOn] = useState<{ lat: number; lon: number } | null>(null);
    const collapsedFor = useRef("");
    const plannedFrom = useRef<{ lat: number; lon: number } | null>(null);
    const originRef = useRef<{ lat: number; lon: number } | null>(null);
    const [pinPoint, setPinPoint] = useState<{ lat: number; lon: number } | null>(null);
    const [pinOpen, setPinOpen] = useState(false);
    const [reportOpen, setReportOpen] = useState(false);

    const [topBarBottom, setTopBarBottom] = useState(0);
    const [sheetBottom, setSheetBottom] = useState(0);
    const [sheetSnap, setSheetSnap] = useState<SheetSnap>("rest");
    const [phoneView, setPhoneView] = useState<PhoneView>("home");
    const [mapMoving, setMapMoving] = useState(false);

    const { destinationId, route, computedAt, loading, error } = routing;
    const { plan, choose, clear, fail } = routing;
    const { location: userLocation, setTracking: setGpsTracking } = gps;

    const gpsFailed = gps.status === "denied"
        || gps.status === "unavailable"
        || gps.status === "outside";
    const startId = gpsFailed && originId === CURRENT_LOCATION ? "" : originId;

    const usingGps = startId === CURRENT_LOCATION;
    const byId = useMemo(() => new Map(locations.map((l) => [l.id, l])), [locations]);

    const resolveOrigin = useCallback(() => {
        if (startId === CURRENT_LOCATION) return userLocation;
        const found = byId.get(startId);
        return found ? { lat: found.lat, lon: found.lon } : null;
    }, [startId, userLocation, byId]);

    const useMyLocation = useCallback(() => {
        setOriginId(CURRENT_LOCATION);
        if (!gps.location) gps.request();
    }, [gps]);

    const centreOnMe = useCallback(() => {
        if (gps.location) setCentreOn({ ...gps.location });
        else gps.request();
    }, [gps]);

    useEffect(() => {
        if (!isDesktop && userLocation) setGpsTracking(true);
    }, [isDesktop, userLocation, setGpsTracking]);

    useEffect(() => {
        if (!gps.watching || !usingGps || !userLocation || !destinationId) return;
        const end = byId.get(destinationId);
        if (!end) return;
        const previous = plannedFrom.current;
        if (previous && metresBetween(previous, userLocation) < REROUTE_THRESHOLD_M) return;
        const timer = setTimeout(() => {
            plannedFrom.current = userLocation;
            plan(userLocation, end, true);
        }, 1000);
        return () => clearTimeout(timer);
    }, [gps.watching, usingGps, userLocation, destinationId, byId, plan]);

    const origin = resolveOrigin();
    useEffect(() => { originRef.current = origin; }, [origin]);
    const hasOrigin = origin !== null;

    useEffect(() => {
        if (!hasOrigin || !destinationId) return;
        const end = byId.get(destinationId);
        if (!end) return;
        const timer = setTimeout(async () => {
            const start = originRef.current;
            if (!start) return;
            await plan(start, end);
            if (collapsedFor.current !== destinationId) {
                collapsedFor.current = destinationId;
                setSheetSnap("rest");
                setSidebarOpen(false);
                setPhoneView("home");
            }
        }, 200);
        return () => clearTimeout(timer);
    }, [hasOrigin, startId, destinationId, byId, plan]);

    const goTo = useCallback((place: MapMarker) => {
        choose(place.id);
        setSheetSnap("rest");
        plannedFrom.current = null;
        if (!isDesktop) setOriginId(CURRENT_LOCATION);
        if (!resolveOrigin()) {
            gps.request();
            fail("Finding your location. It will route as soon as we have it.");
        }
    }, [choose, isDesktop, resolveOrigin, gps, fail]);

    const preview = useCallback((place: MapMarker) => {
        choose(place.id);
        setSheetSnap("rest");
    }, [choose]);

    const clearCategory = useCallback(() => {
        setEmergencyCategory(null);
        setEmergencySubtype(null);
        setSheetSnap("rest");
    }, []);

    const pickCategory = useCallback((category: EmergencyCategory) => {
        setEmergencyCategory(category);
        setEmergencySubtype(null);
        setPhoneView("home");
        setSheetSnap("list");
    }, []);

    const shownTypes = useMemo(() => {
        if (!emergencyCategory || !emergencySubtype) return null;
        const option = categories
            .find((entry) => entry.category === emergencyCategory)?.subtypes
            .find((entry) => entry.key === emergencySubtype);
        return option ? new Set(option.types) : null;
    }, [categories, emergencyCategory, emergencySubtype]);

    const mapLocations = useMemo(() => {
        const keep = (place: MapMarker) =>
            !emergencyCategory
            || place.id === destinationId
            || (place.category === emergencyCategory
                && (!shownTypes || shownTypes.has(place.type)));

        const list: MapMarker[] = locations.filter(keep);
        if (userLocation) {
            list.push({
                id: CURRENT_LOCATION,
                name: "Current Location",
                type: "user",
                category: "user",
                lat: userLocation.lat,
                lon: userLocation.lon,
            });
        }
        return list;
    }, [locations, userLocation, emergencyCategory, shownTypes, destinationId]);

    const activeLocation = useMemo(() => {
        const dest = byId.get(destinationId);
        if (dest) return { lat: dest.lat, lon: dest.lon };
        return centreOn ?? gps.firstFix;
    }, [byId, destinationId, centreOn, gps.firstFix]);

    const coverageQuery = useCoverage(
        coverageOn, coverageMode, traffic, scopeCategories(coverageScope));
    const incidentsQuery = useIncidents();
    const modeEtas = useModeEtas(resolveOrigin(), byId.get(destinationId) ?? null,
                                 traffic);
    const sessionQuery = useSession();
    const sessionRoles = sessionQuery.data?.roles;
    const canAddPlaces = can(sessionRoles, "add_places");
    const canResolve = can(sessionRoles, "resolve_incidents");
    const isAdmin = can(sessionRoles, "manage_roles");
    const coverageActive = coverageOn && !coverageQuery.isError;
    const coverage = coverageActive ? (coverageQuery.data ?? null) : null;
    const coverageError = coverageOn && coverageQuery.isError
        ? errorMessage(coverageQuery.error, "Could not build the coverage map.")
        : "";

    const activeId = destinationId || null;
    const originName = usingGps ? "Current Location" : (byId.get(startId)?.name ?? "");
    const destinationName = byId.get(destinationId)?.name ?? "";
    const arrival = route && computedAt !== null
        ? new Date(computedAt + route.time_min * 60_000)
            .toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : null;

    const analysisMaxHeight =
        `max(120px, calc(100dvh - ${Math.round(topBarBottom + sheetBottom + 190)}px))`;

    const otherCategories = useMemo(
        () => categories.filter((entry) => !styleFor(entry.category).emergency),
        [categories],
    );

    const moreRows: MoreRow[] = useMemo(() => {
        const rows: MoreRow[] = [
            {
                id: "search", label: "Search for a place", Icon: Search,
                hint: "Any building, hall or office on campus",
                onSelect: () => setPhoneView("search"),
            },
            {
                id: "directions", label: "Directions between two places", Icon: Route,
                hint: "Pick your own start and end",
                onSelect: () => setPhoneView("directions"),
            },
            {
                id: "coverage", label: "Response time map", Icon: Radar,
                hint: "Colour every road by how fast help arrives",
                active: coverageActive,
                onSelect: () => {
                    setCoverageOn((on) => !on);
                    setPhoneView("home");
                    setSheetSnap("rest");
                },
            },
            {
                id: "report", label: "Report something", Icon: TriangleAlert,
                hint: "Flooding, a blocked road or a hazard",
                onSelect: () => setReportOpen(true),
            },
            ...otherCategories.map((entry) => ({
                id: `cat-${entry.category}`,
                label: entry.label,
                hint: `${entry.count} ${entry.count === 1 ? "place" : "places"}`,
                Icon: MapPin,
                onSelect: () => pickCategory(entry.category),
            })),
        ];
        if (canAddPlaces) {
            rows.push({
                id: "add-place", label: "Add a place", Icon: MapPinPlus,
                hint: "Use where you are, or pick a spot on the map",
                onSelect: () => {
                    setPinPoint(null);
                    setPinOpen(true);
                },
            });
        }
        if (canResolve) {
            rows.push({
                id: "security", label: "Incident queue", Icon: ShieldAlert,
                hint: "Verify, dismiss and close reports", href: "/security",
            });
        }
        if (isAdmin) {
            rows.push({
                id: "admin", label: "Admin tools", Icon: ShieldCheck,
                hint: "Roles and added places", href: "/admin",
            });
        }
        return rows;
    }, [coverageActive, otherCategories, canAddPlaces, canResolve, isAdmin, pickCategory]);

    const panel = (
        <div className="flex h-full min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 space-y-7 overflow-y-auto px-5 pb-6 pt-1 lg:px-6">
                <div className="pt-3">
                    <ModeTabs value={panelMode} onChange={setPanelMode} />
                </div>

                <div className="-mx-5 lg:-mx-6">
                    <RoleIntroCard
                        roles={sessionRoles}
                        onAddPlace={() => { setPinPoint(null); setPinOpen(true); }}
                        onReport={() => setReportOpen(true)}
                    />
                </div>

                <RouteStops
                    title={panelMode === "emergency" ? "Where are you?" : "Route"}
                    locations={locations}
                    originId={startId}
                    originName={originName}
                    setOriginId={setOriginId}
                    destinationId={destinationId}
                    destinationName={destinationName}
                    setDestinationId={choose}
                    locationsLoading={locationsLoading}
                    getUserLocation={useMyLocation}
                    isWatching={gps.watching}
                    usingGps={usingGps}
                    showDestinationPicker={panelMode === "directions"}
                    onSwap={() => {
                        setOriginId(destinationId);
                        choose(startId);
                    }}
                />

                {panelMode === "emergency" && <EmergencyPicker
                    categories={categories}
                    locations={locations}
                    origin={resolveOrigin()}
                    transportMode={transportMode}
                    trafficLevel={trafficLevel}
                    selectedId={destinationId}
                    active={emergencyCategory}
                    onCategoryChange={setEmergencyCategory}
                    subtype={emergencySubtype}
                    onSubtypeChange={setEmergencySubtype}
                    onSelect={(place) => choose(place.id)}
                    onRequestLocation={useMyLocation}
                    onBrowseAll={() => setPanelMode("directions")}
                />}

                {(error || coverageError || locationsError) && (
                    <div role="alert" className="flex items-start gap-2.5 rounded-2xl bg-red-50 px-3.5 py-3 text-[12px] text-red-700">
                        <TriangleAlert size={15} className="mt-px shrink-0" />
                        <p className="flex-1">{error || coverageError || locationsError}</p>
                    </div>
                )}

                {canAddPlaces && (
                    <button
                        onClick={() => { setPinPoint(null); setPinOpen(true); }}
                        className="flex w-full items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
                    >
                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-900 text-white">
                            <MapPinPlus size={15} />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-[13px] font-semibold text-slate-900">Add a place</span>
                            <span className="block text-[11px] text-slate-500">Use where you are, or long-press the map</span>
                        </span>
                        <ChevronRight size={16} className="shrink-0 text-slate-400" />
                    </button>
                )}

                {canResolve && (
                    <Link
                        href="/security"
                        className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition hover:border-slate-300 hover:bg-slate-50"
                    >
                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-red-600 text-white">
                            <ShieldAlert size={15} />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-[13px] font-semibold text-slate-900">Incident queue</span>
                            <span className="block text-[11px] text-slate-500">Verify, dismiss and close reports</span>
                        </span>
                        <ChevronRight size={16} className="shrink-0 text-slate-400" />
                    </Link>
                )}

                {isAdmin && (
                    <Link
                        href="/admin"
                        className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition hover:border-slate-300 hover:bg-slate-50"
                    >
                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-900 text-white">
                            <ShieldCheck size={15} />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-[13px] font-semibold text-slate-900">Admin tools</span>
                            <span className="block text-[11px] text-slate-500">Roles and added places</span>
                        </span>
                        <ChevronRight size={16} className="shrink-0 text-slate-400" />
                    </Link>
                )}
            </div>
            {isDesktop && (
                <div className="border-t border-slate-100 pt-3">
                    <EmergencyBar />
                </div>
            )}
            <CreatorFooter />
        </div>
    );

    const compactPicker = sheetSnap === "list" && Boolean(emergencyCategory);

    const backRow = (title: string) => (
        <button
            onClick={() => setPhoneView("home")}
            className="flex w-full items-center gap-2 px-5 pb-4 text-left"
        >
            <ChevronLeft size={18} className="shrink-0 text-slate-400" />
            <span className="text-[15px] font-semibold tracking-tight text-slate-900">
                {title}
            </span>
        </button>
    );

    const phoneRest = (
        <>
            {phoneView === "more" && backRow("More")}
            {phoneView === "search" && backRow("Search for a place")}
            {phoneView === "directions" && backRow("Directions")}

            {phoneView === "home" && (
                <RoleIntroCard
                    roles={sessionRoles}
                    onAddPlace={() => { setPinPoint(null); setPinOpen(true); }}
                    onReport={() => setReportOpen(true)}
                />
            )}

            {phoneView === "home" && (route
                ? <RouteSummary
                    route={route}
                    destinationName={destinationName}
                    arrival={arrival}
                    onClear={clear}
                  />
                : <EmergencyFlow
                    categories={categories}
                    active={emergencyCategory}
                    onPick={pickCategory}
                    onClear={clearCategory}
                    compact={compactPicker}
                  />)}

            {phoneView === "home" && (
                <button
                    onClick={() => { setPhoneView("more"); setSheetSnap("list"); }}
                    className="flex w-full items-center justify-between border-t border-slate-100 px-5 py-3 text-left"
                >
                    <span className="text-[13px] font-semibold text-slate-600">
                        More
                    </span>
                    <span className="grid h-8 w-8 place-items-center rounded-xl bg-slate-100 text-slate-500">
                        <SlidersHorizontal size={15} />
                    </span>
                </button>
            )}

            {(error || coverageError || locationsError) && phoneView === "home" && (
                <p role="alert" className="flex items-start gap-2 px-5 pb-3 text-[12px] text-red-700">
                    <TriangleAlert size={14} className="mt-px shrink-0" />
                    {error || coverageError || locationsError}
                </p>
            )}
        </>
    );

    const phoneBody = (() => {
        if (phoneView === "more") return <MoreSheet rows={moreRows} />;
        if (phoneView === "search") {
            return (
                <div className="px-5 pb-6 pt-1">
                    <PlacePicker
                        label="Place"
                        placeholder="Search places on and near campus"
                        selectedId={destinationId}
                        displayValue={destinationName}
                        options={locations}
                        onSelect={(place) => { preview(place); setPhoneView("home"); }}
                        loading={locationsLoading}
                        leading={<Search size={15} className="text-slate-400" />}
                    />
                </div>
            );
        }
        if (phoneView === "directions") {
            return (
                <div className="space-y-6 px-5 pb-6 pt-1">
                    <p className="text-[12.5px] leading-relaxed text-slate-500">
                        Pick a start and an end, or tap <span className="font-semibold text-slate-700">Use my location</span> to
                        start from where you are.
                    </p>
                    <RouteStops
                        title="Route"
                        locations={locations}
                        originId={startId}
                        originName={originName}
                        setOriginId={setOriginId}
                        destinationId={destinationId}
                        destinationName={destinationName}
                        setDestinationId={choose}
                        locationsLoading={locationsLoading}
                        getUserLocation={useMyLocation}
                        isWatching={gps.watching}
                        usingGps={usingGps}
                        showDestinationPicker
                        onSwap={() => {
                            setOriginId(destinationId);
                            choose(startId);
                        }}
                    />
                    {error && (
                        <p role="alert" className="flex items-start gap-2 rounded-2xl bg-red-50 px-3.5 py-3 text-[12px] text-red-700">
                            <TriangleAlert size={15} className="mt-px shrink-0" />
                            {error}
                        </p>
                    )}
                </div>
            );
        }
        if (emergencyCategory) {
            return (
                <NearestList
                    category={emergencyCategory}
                    categories={categories}
                    locations={locations}
                    origin={userLocation}
                    locationStatus={gps.status}
                    locationMessage={gps.message}
                    onRequestLocation={gps.request}
                    transportMode={transportMode}
                    trafficLevel={trafficLevel}
                    subtype={emergencySubtype}
                    onSubtypeChange={setEmergencySubtype}
                    destinationId={destinationId}
                    onGo={goTo}
                    onPreview={preview}
                />
            );
        }
        return (
            <p className="px-5 pb-6 pt-1 text-[12.5px] text-slate-500">
                Choose what you need above, or tap a marker on the map.
            </p>
        );
    })();

    return (
        <main className="relative flex h-[calc(100dvh-var(--acting-offset,0px))] w-full overflow-hidden bg-slate-100 font-sans text-slate-900"
              style={{ marginTop: "var(--acting-offset, 0px)" }}>
            <aside
                aria-label="Route planner"
                inert={!sidebarOpen}
                className={`hidden h-full shrink-0 overflow-hidden bg-white motion-safe:transition-[width] motion-safe:duration-300 motion-safe:ease-out lg:flex ${
                    sidebarOpen ? "w-[380px] border-r border-slate-200/80 xl:w-[412px]" : "w-0"
                }`}
            >
                <div className="flex h-full w-[380px] shrink-0 flex-col xl:w-[412px]">
                    <SidebarHeader
                        locations={locations}
                        onLocationSelect={(loc) => choose(loc.id)}
                        onCollapse={() => setSidebarOpen(false)}
                    />
                    {isDesktop && panel}
                </div>
            </aside>

            <div className="relative flex h-full min-w-0 flex-1 flex-col">
                <div className={isDesktop ? "shrink-0 pt-3" : "contents"}>
                    <TopBar
                        destinationName={destinationName}
                        onClear={clear}
                        transportMode={transportMode}
                        onModeChange={setTransportMode}
                        trafficLevel={trafficLevel}
                        onTrafficChange={setTrafficLevel}
                        etas={modeEtas}
                        routeMinutes={route?.time_min ?? null}
                        loading={loading}
                        inline={isDesktop}
                        compact={!isDesktop && mapMoving}
                        onExpand={() => setMapMoving(false)}
                        onHeightChange={setTopBarBottom}
                    />

                    <RouteAnalysis
                        route={route}
                        transportMode={transportMode}
                        trafficLevel={trafficLevel}
                        navigating={gps.watching && usingGps}
                        inline={isDesktop}
                        hidden={!isDesktop && mapMoving}
                        top={topBarBottom + 8}
                        maxHeight={analysisMaxHeight}
                    />
                </div>

                <div className="relative min-h-0 flex-1">
                <MapComponent
                    locations={mapLocations}
                    activeLocation={activeLocation}
                    activeId={activeId}
                    routeData={route}
                    loadingRoute={loading}
                    serviceBounds={bounds}
                    onUserLocationUpdate={() => setOriginId(CURRENT_LOCATION)}
                    onNavigate={(start, destination) => {
                        choose(destination.id ?? "");
                        plan(start, destination);
                        setSheetSnap("rest");
                    }}
                    onRouteError={fail}
                    onLocateMe={centreOnMe}
                    coverage={coverage}
                    coverageLoading={coverageQuery.isFetching}
                    onToggleCoverage={() => setCoverageOn((on) => !on)}
                    coverageScope={coverageScope}
                    coverageMode={coverageMode}
                    onCoverageModeChange={setCoverageMode}
                    onCoverageScopeChange={setCoverageScope}
                    onLongPress={(point) => {
                        if (!canAddPlaces) return;
                        setPinPoint(point);
                        setPinOpen(true);
                    }}
                    incidents={incidentsQuery.data?.incidents ?? []}
                    onReportIncident={() => setReportOpen(true)}
                    onUserMove={setMapMoving}
                    topBarBottom={isDesktop ? 0 : topBarBottom}
                    sheetBottom={sheetBottom}
                    onContactsOpen={() => setSheetSnap("rest")}
                />
                </div>

                {!sidebarOpen && (
                    <button
                        onClick={() => setSidebarOpen(true)}
                        aria-label="Show route planner"
                        className="absolute left-4 top-4 z-[690] hidden items-center gap-2 rounded-full bg-white/95 px-3.5 py-2.5 text-[12px] font-semibold text-slate-700 shadow-lg ring-1 ring-black/5 backdrop-blur transition hover:text-slate-900 active:scale-95 lg:flex"
                    >
                        <PanelLeftOpen size={15} />
                        Planner
                    </button>
                )}
            </div>

            {!isDesktop && (
                <BottomSheet
                    snap={sheetSnap}
                    onSnapChange={setSheetSnap}
                    label="Emergency panel"
                    onHeightChange={setSheetBottom}
                    rest={phoneRest}
                    footer={phoneView === "more" ? <CreatorFooter /> : null}
                >
                    {phoneBody}
                </BottomSheet>
            )}

            <ReportIncidentDialog
                open={reportOpen}
                onClose={() => setReportOpen(false)}
                point={userLocation}
                outside={gps.status === "outside"}
                locating={gps.status === "locating"}
                onRequestLocation={gps.request}
            />

            {pinOpen && (
                <PinPlaceDialog
                    picked={pinPoint}
                    userLocation={userLocation}
                    locating={gps.status === "locating"}
                    outside={gps.status === "outside"}
                    onRequestLocation={gps.request}
                    categories={categories}
                    onCancel={() => { setPinOpen(false); setPinPoint(null); }}
                    onCreated={(place) => {
                        setPinOpen(false);
                        setPinPoint(null);
                        choose(place.id);
                    }}
                />
            )}
        </main>
    );
}
