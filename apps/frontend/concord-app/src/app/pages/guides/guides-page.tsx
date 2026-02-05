import { useState } from 'react';
import {
  BookOpen,
  Users,
  ShieldCheck,
  Cpu,
  GitBranch,
  FlaskConical,
  Container,
  Server,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { PageHeader } from '../../components/ui/page-header';
import { GuideSection } from '../../types/models';

const guides: GuideSection[] = [
  {
    id: 'inventory',
    title: 'Inventory',
    icon: Cpu,
    steps: [
      {
        title: 'Adding a component',
        description:
          'Navigate to Inventory in the sidebar. Click "New component", fill in the name, category (SoM, Carrier Board, or Accessory), manufacturer, and part number. Click Create. You can then click the card to open the detail view and upload a hero image.',
      },
      {
        title: 'Managing revisions',
        description:
          'Open a component\'s detail view by clicking its card. Use "Add revision" to create inventory revisions (e.g. REV1.0, REV1.1). Each revision has a status: Active, Deprecated, or End of Life.',
      },
      {
        title: 'Creating assemblies',
        description:
          'Switch to the Assemblies tab on the Inventory page. Create an assembly (e.g. "MTIB"), then add revisions with a bill of materials linking specific component revisions and quantities.',
      },
    ],
  },
  {
    id: 'codebases',
    title: 'Codebases & Releases',
    icon: GitBranch,
    steps: [
      {
        title: 'Registering a codebase',
        description:
          'Navigate to Codebases in the sidebar. Click "New codebase" and enter the name (e.g. "Concord App", "Concord OS"), an optional repository URL, default branch, and description. Click Create.',
      },
      {
        title: 'Creating a release',
        description:
          'Click a codebase card to open its detail view. Click "Add release" and fill in the version (e.g. 1.0.0), status (Draft, Released, or Deprecated), optional tag name for Bitbucket linking, and release notes. When you set status to Released, the release date is recorded automatically.',
      },
      {
        title: 'Uploading artifacts',
        description:
          'Expand a release row by clicking it. Use "Upload file" to drag-and-drop or select a file — it will be stored in MinIO with a SHA-256 checksum. Use "Add external link" to reference files hosted elsewhere. Artifacts can be downloaded or deleted from the artifacts table.',
      },
    ],
  },
  {
    id: 'tests',
    title: 'Tests & Validation',
    icon: FlaskConical,
    steps: [
      {
        title: 'Defining tests',
        description:
          'Tests are defined per product with a name, category (e.g. electrical, firmware, post), and sort order for sequential execution. Each test can include a default config template that can be overridden per execution.',
      },
      {
        title: 'Running a session',
        description:
          'Create a session for a product, optionally tied to a fixture. Set a target count or leave it open-ended. Devices are registered by serial number and go through PENDING → IN_PROGRESS → PASSED/FAILED as tests execute.',
      },
      {
        title: 'Reviewing results',
        description:
          'Each test execution records step-by-step results with pass/fail status and measurement data. View results by session, device, or across all executions for a test.',
      },
    ],
  },
  {
    id: 'deployments',
    title: 'Deployments',
    icon: Container,
    steps: [
      {
        title: 'Deploying software',
        description:
          'Deployments track software running on the cluster — test runners, operators, MTIB servers, etc. Each deployment has a status (Pending, Running, Stopped, Failed), K8s manifest config, version, and product association.',
      },
      {
        title: 'Monitoring status',
        description:
          'The Deployments page shows all tracked deployments with their current status. Live K8s state is queried alongside the recorded intent to surface any drift.',
      },
    ],
  },
  {
    id: 'nodes',
    title: 'Nodes (MTIBs)',
    icon: Server,
    steps: [
      {
        title: 'Registering a node',
        description:
          'Nodes represent compute hardware in the cluster (typically MTIB boards). Each node has a hostname (must be unique), type (Manufacturing or Validation), IP address, and inventory revision info.',
      },
      {
        title: 'Assigning to fixtures',
        description:
          'Nodes are assigned to fixture slots — each slot maps to one MTIB. A node can only be assigned to one slot at a time. Unassign by setting the slot\'s nodeId to null.',
      },
    ],
  },
  {
    id: 'history',
    title: 'History & Audit Log',
    icon: ShieldCheck,
    steps: [
      {
        title: 'Viewing the audit log',
        description:
          'Navigate to History in the admin section of the sidebar. The page shows a chronological feed of all actions performed across the system over the past 30 days, including who did what, when, and to which entity.',
      },
      {
        title: 'Filtering entries',
        description:
          'Use the search box to filter by action name (e.g. "create", "delete") or the entity type dropdown to narrow results to a specific model (User, InventoryComponent, Release, etc.). Filters apply immediately and reset pagination to page 1.',
      },
      {
        title: 'Viewing details',
        description:
          'Click any row that has a chevron indicator to expand its details. This shows the contextual data captured at the time of the action — for example the name, email, or fields that were changed. Details also include the IP address and full timestamp.',
      },
    ],
  },
  {
    id: 'users',
    title: 'Users & Permissions',
    icon: Users,
    steps: [
      {
        title: 'Pre-registering a user',
        description:
          'Go to Users in the sidebar. Click "Pre-register user" and enter their email and name. Assign a permission set. The user can then log in via Google OAuth — their account is matched by email.',
      },
      {
        title: 'Managing permission sets',
        description:
          'Go to Permission Sets. Create or edit sets that bundle permissions together (e.g. "Admin", "Operator", "Viewer"). Each set contains a list of permission strings like "Concord.Admin.Users.View".',
      },
      {
        title: 'Understanding permissions',
        description:
          'Permissions follow the pattern Concord.<Area>.<Resource>.<Action>. View permissions grant read access, Manage permissions grant write/delete access. Users without a permission set cannot access any protected features.',
      },
    ],
  },
];

export function GuidesPage() {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set()
  );

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Guides"
          description="How-to guides for each part of the Concord system."
        />
      </div>

      <div className="space-y-2">
        {guides.map((guide) => {
          const Icon = guide.icon;
          const isExpanded = expandedSections.has(guide.id);

          return (
            <div
              key={guide.id}
              className="rounded-xl border border-border bg-surface-1"
            >
              <button
                onClick={() => toggleSection(guide.id)}
                className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-surface-2 rounded-xl transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown size={16} className="shrink-0 text-text-tertiary" />
                ) : (
                  <ChevronRight size={16} className="shrink-0 text-text-tertiary" />
                )}
                <Icon size={18} strokeWidth={1.75} className="shrink-0 text-accent" />
                <span className="text-sm font-semibold text-text-primary">
                  {guide.title}
                </span>
                <span className="ml-auto text-2xs text-text-tertiary">
                  {guide.steps.length} step{guide.steps.length !== 1 ? 's' : ''}
                </span>
              </button>

              {isExpanded && (
                <div className="border-t border-border px-5 py-4">
                  <ol className="space-y-4">
                    {guide.steps.map((step, i) => (
                      <li key={step.title || `step-${i}`} className="flex gap-3">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-muted text-2xs font-semibold text-accent">
                          {i + 1}
                        </span>
                        <div>
                          <h4 className="text-sm font-medium text-text-primary">
                            {step.title}
                          </h4>
                          <p className="mt-1 text-sm leading-relaxed text-text-secondary">
                            {step.description}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
