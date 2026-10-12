export type OutputType = 
  | 'linkedin' 
  | 'twitter' 
  | 'advisory' 
  | 'infographic' 
  | 'executive_summary' 
  | 'presentation' 
  | 'video';

export type AudienceType = 
  | 'General Public' 
  | 'Executives' 
  | 'Government Officials' 
  | 'Technical Team' 
  | 'Security Team' 
  | 'Customers' 
  | 'Students' 
  | 'Custom';

export type ToneType = 
  | 'Professional' 
  | 'Formal' 
  | 'Informative' 
  | 'Persuasive' 
  | 'Urgent' 
  | 'Friendly' 
  | 'Technical';

export type LanguageType = 
  | 'English' 
  | 'Tamil' 
  | 'Hindi' 
  | 'Malayalam'
  | 'Telugu'
  | 'Kannada'
  | 'French' 
  | 'German' 
  | 'Japanese'
  | 'Spanish' 
  | 'Custom';

export type DetailLevel = 'Concise' | 'Balanced' | 'Detailed';

export type ObjectiveType = 
  | 'Inform' 
  | 'Educate' 
  | 'Alert' 
  | 'Persuade' 
  | 'Summarize' 
  | 'Engage' 
  | 'Brief';

export type ContentStyle = 
  | 'Professional' 
  | 'Executive' 
  | 'Technical' 
  | 'Social Media' 
  | 'News Style' 
  | 'Storytelling' 
  | 'Academic' 
  | 'Custom';

export type CoreSystemStatus = 'ready' | 'verified' | 'processing' | 'active' | 'needs_review' | 'failed';

export interface SourceFile {
  id: string;
  sourceId?: string;
  fileId?: string;
  projectId?: string;
  name: string;
  type: 'PDF' | 'DOCX' | 'TXT' | 'IMAGE' | 'VIDEO' | 'TEXT';
  size: string;
  pages?: number;
  extractedText: string;
  status: CoreSystemStatus | string;
  uploadedAt: string;
  extraction?: { pageCount?: number; textLength?: number; wordCount?: number };
  normalized?: {
    text?: { content?: string; characterCount?: number };
    pages?: Array<{ pageNumber?: number; text?: string }>;
    sections?: unknown[];
    tables?: unknown[];
    images?: unknown[];
    metadata?: Record<string, unknown>;
  };
  processing?: { status?: string; stage?: string; progress?: number; error?: string | null };
  doclinkResult?: Record<string, unknown>;
  analysisResult?: Record<string, unknown>;
  uckrReference?: { uckrId?: string; version?: number; status?: string };
}

export interface AIAnalysis {
  detectedTopic: string;
  confidenceScore: number;
  keyEntities: string[];
  importantFacts: string[];
  audienceSignals: string[];
  communicationObjective: string;
  sentiment: string;
  readabilityScore: string;
}

// ==========================================
// UCKR: Unified Content Knowledge Representation
// ==========================================

export type UckrFactType = 'Metric' | 'Proposition' | 'Entity Finding' | 'Timeline / Event' | 'Action Mandate' | 'Risk / Impact';

export interface UckrFact {
  id: string; // e.g. "F-001"
  factId?: string;
  value: string;
  type: UckrFactType;
  sourceDoc: string;
  page: number;
  section: string;
  confidence: number;
  quote: string;
  usedInDeliverables: OutputType[];
}

export type UckrEntityCategory = 
  | 'Actor / Stakeholder' 
  | 'Organization' 
  | 'Technology / Standard' 
  | 'Specification' 
  | 'Infrastructure / Asset'
  | 'Policy / Regulation';

export interface UckrEntity {
  id: string;
  name: string;
  category: UckrEntityCategory;
  mentions: number;
  role: string;
}

export interface UckrEvent {
  id: string;
  title: string;
  timestamp: string;
  impact: string;
  actors: string[];
}

export interface UckrTimelineNode {
  id: string;
  description: string;
  duration_value?: number | null;
  duration_unit?: string | null;
  sequence?: number | null;
  kind?: 'total' | 'phase' | 'milestone' | string;
  sourceFactId?: string | null;
  sourceText?: string;
  startRelationship?: string | null;
  endRelationship?: string | null;
}

export interface UckrMetric {
  id: string;
  name: string;
  value: string;
  unit?: string;
  context: string;
  confidence: number;
}

export interface UckrRelationship {
  id: string;
  source: string;
  relation: string;
  target: string;
  confidence: number;
}

export interface UckrAction {
  id: string;
  action: string;
  priority: 'P0 Immediate' | 'P1 High' | 'P2 Medium';
  timeframe: string;
  owner: string;
}

export interface UckrSourceRef {
  id: string;
  title: string;
  page: number;
  section: string;
  excerpt: string;
}

export interface UckrKnowledgeBase {
  id?: string;
  uckrId?: string;
  projectId?: string;
  sourceId?: string;
  version?: number;
  status?: string;
  statistics?: {
    totalFacts: number;
    totalEntities: number;
    totalEvents: number;
    totalTimelineNodes?: number;
    timelineConsistent?: boolean | null;
    timelineTotalDuration?: number | null;
    timelineDurationUnit?: string | null;
    timelinePhaseCount?: number;
    totalMetrics: number;
    totalClaims?: number;
    totalActions: number;
    totalSources: number;
    totalRelationships: number;
    coverage: number;
    grounding: number;
    readiness: string | number;
  };
  stats: {
    totalFacts: number;
    totalEntities: number;
    totalEvents: number;
    totalTimelineNodes?: number;
    timelineConsistent?: boolean | null;
    timelineTotalDuration?: number | null;
    timelineDurationUnit?: string | null;
    timelinePhaseCount?: number;
    totalMetrics: number;
    totalActions: number;
    totalSources: number;
    totalRelationships: number;
    coverage: number; // e.g. 96%
    grounding: number; // e.g. 99%
    groundingIndex?: number;
    factCompleteness?: number;
    factConsistency?: number;
    entityConsistency?: number;
    numberConsistency?: number;
    dateConsistency?: number;
    readiness: number; // e.g. 98%
  };
  facts: UckrFact[];
  entities: UckrEntity[];
  events: UckrEvent[];
  timeline?: UckrTimelineNode[];
  metrics: UckrMetric[];
  claims?: any[];
  relationships: UckrRelationship[];
  actions: UckrAction[];
  sources: UckrSourceRef[];
  validation?: {
    timelineConsistency?: {
      consistent?: boolean | null;
      declared_total?: number;
      calculated_total?: number;
      duration_unit?: string;
      phase_count?: number;
    };
  };
  createdAt?: string;
  updatedAt?: string;
}

export interface TransformationConfig {
  targetAudience: AudienceType;
  tone: ToneType;
  language: LanguageType;
  levelOfDetail: DetailLevel;
  objective: ObjectiveType;
  contentStyle: ContentStyle;
  customNotes?: string;
}

export interface LinkedInDeliverable {
  hook: string;
  body: string;
  callToAction: string;
  hashtags: string[];
  characterCount: number;
  targetAudience: string;
  generatedImage?: {
    id: string;
    style: string;
    headline: string;
    subheadline: string;
    createdAt: string;
  };
}

export interface TwitterDeliverable {
  singlePost: string;
  thread: {
    index: number;
    text: string;
    charCount: number;
  }[];
}

export interface AdvisoryDeliverable {
  advisoryId: string;
  title: string;
  domain?: 'education' | 'cybersecurity' | 'healthcare' | 'finance' | 'technology' | 'general' | string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'INFORMATIONAL';
  dateIssued: string;
  situation: string;
  keyInformation: string[];
  threatImpact: string;
  recommendedActions: {
    phase: string;
    steps: string[];
  }[];
  complianceReferences: string[];
}

export interface DeliverableValidationResult {
  outputType: OutputType;
  status: 'verified' | 'needs_review' | 'failed';
  groundingScore: number;
  supportedClaimsCount: number;
  unsupportedClaims: string[];
  unsupportedMetrics: string[];
  metricsConsistent: boolean;
  factsConsistent: boolean;
  entitiesConsistent: boolean;
}

export interface ExecutiveSummaryDeliverable {
  priority: 'High' | 'Critical' | 'Medium' | 'Low';
  keyFindingsCount: number;
  recommendationsCount: number;
  executiveOverview: string;
  keyFindings: {
    metric?: string;
    title: string;
    description: string;
  }[];
  implications: string[];
  strategicActions: string[];
}

export interface InfographicDeliverable {
  keyMessage: string;
  keyStatistics: {
    value: string;
    label: string;
    subtext: string;
  }[];
  supportingPoints: {
    iconName: string;
    title: string;
    description: string;
  }[];
  callToAction: string;
  layoutRecommendation: 'Vertical' | 'Horizontal' | 'Timeline' | 'Process' | 'Comparison';
  visualStyle: 'Corporate' | 'Minimal' | 'Editorial' | 'Technology';
}

export interface PresentationSlide {
  slideNumber: number;
  title: string;
  subtitle?: string;
  bullets: string[];
  column_left?: string[];
  column_right?: string[];
  visualRecommendation: string;
  visual_recommendation?: string;
  speakerNotes: string;
  speaker_notes?: string;
}

export interface PresentationDeliverable {
  deckTitle: string;
  presentation_title?: string;
  subtitle?: string;
  totalSlides: number;
  theme?: string;
  slides: PresentationSlide[];
}

export interface VideoScene {
  sceneNumber: number;
  title: string;
  durationSeconds: number;
  sceneDescription: string;
  visualRecommendation: string;
  narration: string;
  onScreenText: string;
}

export interface VideoDeliverable {
  title: string;
  aspectRatio: '16:9' | '9:16' | '1:1';
  style: 'Professional' | 'News' | 'Documentary' | 'Corporate';
  totalDurationSeconds: number;
  script: string;
  scenes: VideoScene[];
  subtitlesSrt: string;
}

export interface TransformationDeliverables {
  linkedin?: LinkedInDeliverable;
  twitter?: TwitterDeliverable;
  advisory?: AdvisoryDeliverable;
  infographic?: InfographicDeliverable;
  executive_summary?: ExecutiveSummaryDeliverable;
  executiveSummary?: ExecutiveSummaryDeliverable;
  presentation?: PresentationDeliverable;
  video?: VideoDeliverable;
}

export interface TransformationProject {
  id: string;
  projectId?: string;
  userId?: string;
  name?: string;
  projectName?: string;
  title: string;
  description: string;
  source: SourceFile;
  config: TransformationConfig;
  selectedOutputs: OutputType[];
  analysis: AIAnalysis;
  uckr?: UckrKnowledgeBase;
  deliverables?: TransformationDeliverables;
  status: CoreSystemStatus | string;
  updatedAt: string;
  createdAt: string;
}

export interface AIAgent {
  id: string;
  name: string;
  role: string;
  description: string;
  status: CoreSystemStatus | string;
  version?: string;
  tasksCompleted: number;
  latencyMs?: number;
  accuracy: string | number;
  color?: string;
  model?: string;
}

export interface MCPIntegration {
  id: string;
  name: string;
  category?: 'Social Publishing' | 'Communication' | 'Storage' | 'Developer Tools';
  description: string;
  icon: string;
  isConnected: boolean;
  status?: CoreSystemStatus | string;
  endpoint?: string;
  capabilities?: string[];
  lastSync?: string;
  webhookUrl?: string;
  automatedDeliverable?: OutputType;
}

export type DeliverablesState = TransformationDeliverables;
export type ProjectRecord = TransformationProject;
export type AgentInfo = AIAgent;
export type McpIntegration = MCPIntegration;



export type ViewState = 
  | 'dashboard' 
  | 'new_transformation' 
  | 'generation_pipeline' 
  | 'results' 
  | 'projects' 
  | 'outputs' 
  | 'uckr'
  | 'agents' 
  | 'mcp' 
  | 'image_studio'
  | 'settings';
