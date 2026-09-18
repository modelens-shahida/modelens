/**
 * ModeLens Full Platform Navigation Tree & Hierarchy Specifications
 * Defines the complete sitemap as requested in Shahida's design directives.
 */

import {
  LayoutDashboard,
  Sparkles,
  Camera,
  PenTool,
  Grid,
  Video,
  FolderKanban,
  ShoppingBag,
  Users,
  Move,
  Image as ImageIcon,
  Layers,
  CheckSquare,
  PackageCheck,
  UserGroup,
  CreditCard,
  Key,
  Settings,
  ShieldAlert,
} from "lucide-react";

export const NAVIGATION_SITEMAP = [
  {
    group: "OVERVIEW",
    items: [
      { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard, badge: null },
      { name: "Create Production", href: "/dashboard/create", icon: Sparkles, badge: "NEW" },
    ],
  },
  {
    group: "STUDIOS",
    items: [
      { name: "Ghost Studio", href: "/dashboard/ghost", icon: Camera, desc: "Flat Lay & Mannequin to Model" },
      { name: "Sketch Studio", href: "/dashboard/sketch", icon: PenTool, desc: "CAD & Garment Visualization" },
      { name: "Catalog Studio", href: "/dashboard/catalog", icon: Grid, desc: "E-Commerce Batch Production" },
      { name: "Move Studio", href: "/dashboard/move", icon: Video, desc: "AI Fashion Video & Motion" },
    ],
  },
  {
    group: "LIBRARY",
    items: [
      { name: "Projects", href: "/dashboard/campaigns", icon: FolderKanban, count: 12 },
      { name: "Products", href: "/dashboard/assets", icon: ShoppingBag, count: 48 },
      { name: "Characters", href: "/dashboard/characters", icon: Users, badge: "Casting Board" },
      { name: "Poses & Angles", href: "/dashboard/angle-shots", icon: Move, count: 24 },
      { name: "Backgrounds", href: "/dashboard/fluid", icon: ImageIcon, count: 18 },
      { name: "Assets", href: "/dashboard/admin/assets", icon: Layers, count: 142 },
    ],
  },
  {
    group: "PRODUCTION",
    items: [
      { name: "Generations & Jobs", href: "/dashboard/jobs", icon: Layers, activeCount: 2 },
      { name: "Results Grid", href: "/dashboard/results/latest", icon: ImageIcon, count: 16 },
      { name: "Review & QA", href: "/dashboard/fix-requests", icon: CheckSquare, alertCount: 4 },
      { name: "Batch Production", href: "/dashboard/catalog", icon: PackageCheck, badge: "Bulk" },
    ],
  },
  {
    group: "ORGANIZATION",
    items: [
      { name: "Team Members", href: "/dashboard/brands", icon: UserGroup },
      { name: "Billing & Credits", href: "/dashboard/billing", icon: CreditCard },
      { name: "API & Webhooks", href: "/dashboard/webhooks", icon: Key },
      { name: "Workspace Settings", href: "/dashboard/settings", icon: Settings },
    ],
  },
  {
    group: "ADMINISTRATION",
    items: [
      { name: "Admin Dashboard", href: "/dashboard/admin-stats", icon: ShieldAlert, badge: "Internal" },
    ],
  },
];
