"""Prompts da LLM para a wiki e o checklist técnico (Fase 9, fonte trocada na Fase 10).

Entrada: ingestion_payloads do atlas-apis-ingestao (antes era document_context — a
estrutura central dos dados é idêntica entre as duas collections). Os campos de
negócio (ownership, cmdb, api, integrations, security, runtime, deployment etc.)
sempre chegam aqui com o valor final, seja ele de origem REAL ou MOCK (o dicionário
'sources' do payload é só metadado de auditoria de proveniência — DEV usa MOCK por
indisponibilidade do DevConsole, Produção terá REAL nos mesmos campos, sem exigir
nenhuma mudança de código aqui). Os campos puramente de diagnóstico de ingestão —
processing, sources, completeness, ingestion_diagnostics, ingestion_key,
schema_version — não entram no prompt, pois não agregam valor ao conteúdo da
documentação gerada.
Saída: JSON com chaves em inglês (ver docs/RENOMEACAO_CAMPOS.md). O histórico das
correções C1-C6 está no git.
"""

import json
from typing import Any


def _json(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _formatar_document_context(document_context: dict[str, Any]) -> str:
    """Formata o document_context em texto legível, igual para os dois prompts."""
    (cmdb, ownership, classification, technology, api, integrations, security,
     observability, data, runtime, quality, deployment, jira) = (
        document_context.get(chave, {}) for chave in (
            "cmdb", "ownership", "classification", "technology", "api", "integrations",
            "security", "observability", "data", "runtime", "quality", "deployment", "jira"))

    endpoints_resumo = [
        f"{metodo} {item.get('path')} ({item.get('operation_id')})"
        for metodo, lista in api.get("exposed_endpoints", {}).items()
        for item in lista
    ]
    consumidos, consumidores = integrations.get("consumed", {}), integrations.get("consumers", {})

    contrato = api.get("openapi_contract", {})
    openapi_preenchido = bool(contrato.get("content") or contrato.get("contents"))
    openapi_detalhe = (
        f" (host: {contrato.get('host')}, ambiente: {contrato.get('environment')})"
        if openapi_preenchido and contrato.get("host") else ""
    )

    cmdb_texto = "(nenhum dado de CMDB associado)"
    if cmdb:
        dominios = ", ".join(d.get("name", "") for d in cmdb.get("service_domains", []))
        cmdb_texto = f"""- Chave do componente no CMDB: {cmdb.get('component_key') or '(não informada)'}
- Nome oficial da aplicação: {cmdb.get('application', {}).get('name') or '(não informado)'}
- Código do time (CMDB): {cmdb.get('team', {}).get('code') or '(não informado)'}
- Grupo aprovador: {cmdb.get('team', {}).get('approving_group') or '(não informado)'}
- Domínios de serviço: {dominios or '(nenhum)'}"""

    deployments_texto = "\n".join(
        f"- {ambiente}: versão {info.get('version')}, "
        f"último deploy em {info.get('created_at')} por {info.get('updated_by')}"
        for ambiente, info in (deployment.get("deployments", {}) or {}).items()
    ) or "(sem histórico de deploy por ambiente)"

    return f"""### Identificação
- Nome: {document_context.get('component_name')}
- Descrição: {document_context.get('description') or '(não informada)'}
- Status: {document_context.get('status')}
- Categoria: {document_context.get('category')}
- Visibilidade: {document_context.get('visibility')}
- Repositório: {document_context.get('repository')}

### CMDB (dados de governança/inventário corporativo)
{cmdb_texto}

### Ownership (responsabilidade organizacional) — use campos ricos quando presentes
- Time responsável: {ownership.get('responsible_team') or '(não informado)'}
- Tribo: {ownership.get('tribe', {}).get('name') or '(não informada)'}
- Projeto: {ownership.get('project') or '(não informado)'}
- Aprovadores: {json.dumps(ownership.get('approvers') or [], ensure_ascii=False)}
- Tech leads: {json.dumps(ownership.get('tech_leads') or [], ensure_ascii=False)}
- Arquitetos: {json.dumps(ownership.get('architects') or [], ensure_ascii=False)}
- Desenvolvedores: {json.dumps(ownership.get('developers') or [], ensure_ascii=False)}
- QA: {json.dumps(ownership.get('qa') or [], ensure_ascii=False)}
- UX: {json.dumps(ownership.get('ux') or [], ensure_ascii=False)}
- Colaboradores temporários: {json.dumps(ownership.get('temporary_contributors') or [], ensure_ascii=False)}
- Times colaboradores: {json.dumps(ownership.get('contributor_teams') or [], ensure_ascii=False)}

### Classificação técnica
- Tipo de aplicação: {classification.get('application_type')}
- Linguagem principal: {classification.get('main_language')}
- Framework principal: {classification.get('main_framework')}

### Tecnologias declaradas
{json.dumps(technology.get('technologies', []), ensure_ascii=False)}

### Estrutura de pacotes (parcial)
{json.dumps(technology.get('package_structure', [])[:30], ensure_ascii=False)}

### Endpoints expostos pela API (total: {len(endpoints_resumo)})
{chr(10).join(endpoints_resumo) if endpoints_resumo else '(nenhum endpoint listado)'}

Contrato OpenAPI formal preenchido: {'sim' + openapi_detalhe if openapi_preenchido else 'não'}

### Integrações — o que este componente CONSOME (por ambiente)
{json.dumps(consumidos, ensure_ascii=False, indent=2)}

### Integrações — quem CONSOME este componente (por ambiente)
{json.dumps(consumidores, ensure_ascii=False, indent=2)}

### Segurança
- Autenticação de aplicação: {json.dumps(security.get('authentication', {}).get('application', []), ensure_ascii=False)}
- Autenticação de infraestrutura: {json.dumps(security.get('authentication', {}).get('infrastructure', []), ensure_ascii=False)}

### Observabilidade
- Habilitados: {observability.get('enabled') or '(nenhum)'}
- Desabilitados: {observability.get('disabled') or '(nenhum)'}

### Dados
- Bancos de dados: {data.get('databases') or '(nenhum informado)'}

### Runtime e infraestrutura
- Funcionalidades habilitadas: {runtime.get('enabled_features') or '(nenhuma)'}
- Ambientes com recursos: {runtime.get('resources_by_environment') or '(nenhum)'}
- Provedor de nuvem: {runtime.get('cloud_provider') or '(não informado)'}
- Clusters: {json.dumps(runtime.get('clusters', {}), ensure_ascii=False)}
- DNS interno por ambiente: {json.dumps(runtime.get('dns', {}).get('internal', {}), ensure_ascii=False)}
- DNS externo por ambiente: {json.dumps(runtime.get('dns', {}).get('external', {}), ensure_ascii=False)}

### Qualidade
- Criticidade: {quality.get('criticality') or '(não informada)'}
- Score: {quality.get('score')}

### Deploy
- Branch padrão: {deployment.get('default_branch')}
- Pipeline de deploy: {deployment.get('pipeline_deploy') or '(não informado)'}
- Histórico de deploy por ambiente:
{deployments_texto}

### Jira
- Épicos: {jira.get('epics') or '(nenhum)'}
- Roadmap: {jira.get('roadmap') or '(nenhum)'}
- Responsável funcional: {jira.get('functional_owner') or '(não informado)'}"""


# Caminhos reais do ingestion_payloads (antes document_context — mesma estrutura
# central) que a LLM pode citar em "sources_used".
CAMINHOS_VALIDOS_DOCUMENT_CONTEXT = """component_name, description, status, category, visibility, repository,
cmdb.component_key, cmdb.application.name, cmdb.team.code, cmdb.team.approving_group, cmdb.service_domains,
ownership.responsible_team, ownership.tribe.name, ownership.project, ownership.approvers,
ownership.tech_leads, ownership.architects, ownership.developers, ownership.qa, ownership.ux,
ownership.temporary_contributors, ownership.contributor_teams,
classification.application_type, classification.main_language, classification.main_framework,
technology.technologies, technology.package_structure,
api.exposed_endpoints, api.openapi_contract,
integrations.consumed, integrations.consumers,
security.authentication.application, security.authentication.infrastructure,
observability.enabled, observability.disabled,
data.databases,
runtime.enabled_features, runtime.resources_by_environment, runtime.cloud_provider, runtime.clusters,
runtime.dns.internal, runtime.dns.external,
quality.criticality, quality.score,
deployment.default_branch, deployment.pipeline_deploy, deployment.deployments,
jira.epics, jira.roadmap, jira.functional_owner"""


SYSTEM_WIKI_DOCUMENTACAO = f"""Você é um especialista em documentação técnica de software, \
com profundo conhecimento em arquitetura de sistemas e boas práticas de engenharia.

Seu papel é analisar o contexto estruturado de um componente de software — já coletado e \
normalizado por um sistema interno de inventário — e gerar uma documentação completa em \
formato de WIKI, organizada em seções.

Regra crítica de ESTILO — leia com atenção, ela evita um erro observado na prática:
- Escreva SEMPRE em prosa corrida e sintetizada, como um redator humano escreveria
- NUNCA use o formato de rótulo "Campo: valor" ou listas de "**Nome:** valor" — um leitor
  não deve perceber que os dados vieram de uma estrutura de campos; a documentação deve
  ler como texto, não como uma reformatação do JSON de origem
- Quando uma lista tiver mais de 5 itens (ex: endpoints, tecnologias), NÃO liste todos —
  agrupe por padrão/categoria, mencione a contagem total, e cite apenas os mais
  representativos como exemplo (ex: "a API expõe 19 endpoints, majoritariamente de
  consulta (GET), como listagem de componentes e times")

Regras obrigatórias de conteúdo:
- Escreva em português brasileiro formal e técnico
- Baseie-se APENAS nos dados fornecidos — não adicione suposições
- NUNCA invente informações que não estejam nos dados fornecidos
- Quando um campo estiver vazio, nulo, ou com lista vazia, mencione isso de forma neutra
  (ex: "não há aprovadores cadastrados") — NÃO presuma o motivo
- Quando os campos de ownership detalhado estiverem preenchidos (aprovadores, QA, UX,
  colaboradores temporários, times colaboradores), aproveite-os na Visão Geral para
  descrever a composição real do time — só mencione o que realmente estiver presente
- Quando houver dados de CMDB, use o nome oficial da aplicação e o grupo aprovador
  para enriquecer a Visão Geral, se agregarem contexto útil
- Quando houver histórico de deploy por ambiente, mencione em qual ambiente o
  componente está mais atualizado e se há defasagem de versão entre ambientes

Regra crítica de ESTRUTURA DE SAÍDA — leia com atenção, ela evita um erro observado na prática:
- Cada seção do JSON de resposta deve ter EXATAMENTE estes 4 campos, nenhum a mais:
  "title", "order", "content_markdown", "sources_used"
- NUNCA crie campos adicionais como "diagram_content", "summary" ou qualquer outro nome —
  se você gerar um diagrama Mermaid (seção 3), ele deve ficar DENTRO da própria string de
  "content_markdown" daquela seção, como parte do mesmo texto markdown

Regra sobre o campo "sources_used" — leia com atenção, ela evita um erro observado na
prática (a LLM às vezes traduz ou simplifica nomes de campos, tornando a citação inútil
para auditoria):
- Cite SOMENTE caminhos EXATOS da lista abaixo, escritos exatamente como aparecem aqui
  (em inglês, com a pontuação e capitalização exatas) — NUNCA traduza, NUNCA invente
  sub-caminhos, NUNCA simplifique (ex: "status" está certo; "identificacao.status" está
  errado)
- Lista de caminhos válidos:
  {CAMINHOS_VALIDOS_DOCUMENT_CONTEXT}
- Se uma seção não usar diretamente nenhum desses campos, use uma lista vazia []

Auto-checagem antes de responder (aplique mentalmente, sem custo de nova chamada):
- Releia cada frase: ela corresponde a um fato presente nos dados? "Corresponder" NÃO
  significa copiar o campo literalmente — reescrever com suas palavras é o esperado
- Se uma frase não tiver correspondência com nenhum dado fornecido, remova-a
- Confira se cada "sources_used" citada está literalmente na lista de caminhos válidos
- Confira se cada seção tem exatamente os 4 campos esperados ("title", "order",
  "content_markdown", "sources_used"), sem nenhum campo extra

Retorne APENAS um JSON válido — sem texto antes ou depois, sem blocos de código markdown \
fora da estrutura pedida.

Sobre as seções — gere exatamente 5, na ordem abaixo:
  1. Visão Geral — o que é o componente, quem é responsável, status, criticidade
  2. Arquitetura e Endpoints — API exposta, rotas principais (resumidas por padrão se
     forem muitas), contrato OpenAPI
  3. Integrações e Dependências — o que consome e quem consome este componente, em
     prosa, seguida (dentro do MESMO content_markdown desta seção) de um diagrama
     Mermaid (```mermaid ... ```) do tipo "graph LR" representando essas mesmas
     relações — use o nome do componente (component_name) como identificador do nó
     central do diagrama, não o hostname/DNS completo, para manter o diagrama legível
  4. Segurança e Observabilidade — autenticação e ferramentas de observabilidade
  5. Dados e Infraestrutura — bancos de dados, runtime, deploy (incluindo o histórico
     de versões por ambiente, quando disponível)"""


# (título, conteúdo de exemplo, fontes) de cada seção da wiki, na ordem de saída.
_SECOES_WIKI = (
    ("Visão Geral", "...", ("ownership.responsible_team", "quality.criticality")),
    ("Arquitetura e Endpoints", "...", ("api.exposed_endpoints", "api.openapi_contract")),
    ("Integrações e Dependências",
     "texto em prosa descrevendo as integrações...\\n\\n```mermaid\\ngraph LR\\ncomponent_name --> outro-componente\\n```",
     ("integrations.consumed", "integrations.consumers")),
    ("Segurança e Observabilidade", "...",
     ("security.authentication.application", "observability.enabled")),
    ("Dados e Infraestrutura", "...", ("data.databases", "deployment.deployments")),
)


def montar_prompt_wiki_documentacao(document_context: dict[str, Any]) -> str:
    """Monta a mensagem do usuário para gerar a wiki (5 seções)."""
    secoes = ",\n".join(
        f'    {{\n      "title": "{titulo}",\n      "order": {ordem},\n'
        f'      "content_markdown": "{conteudo}",\n      "sources_used": {json.dumps(fontes)}\n    }}'
        for ordem, (titulo, conteudo, fontes) in enumerate(_SECOES_WIKI, 1)
    )
    return f"""Analise os dados abaixo de um componente e gere uma documentação completa \
em formato de wiki, organizada em seções.

{_formatar_document_context(document_context)}

## O que gerar

Retorne um JSON com este formato exato — cada seção tem EXATAMENTE 4 campos, nunca mais:

{{
  "general_title": "nome do componente — Documentação Técnica",
  "sections": [
{secoes}
  ]
}}

Repare no exemplo da seção 3: o bloco ```mermaid``` está DENTRO da mesma string de \
"content_markdown", usando o nome do componente como nó, não o hostname completo.

Lembre-se: prosa corrida, sem rótulos "Campo: valor", listas longas resumidas por \
categoria, e sources_used usando apenas os caminhos exatos da lista fornecida nas \
instruções do sistema."""


SYSTEM_CHECKLIST_TECNICO = """Você é um especialista em análise técnica e catalogação \
de componentes de software em grandes organizações de tecnologia.

Seu papel é preencher um checklist técnico fixo para um componente, usando SOMENTE os \
dados estruturados fornecidos — que já vêm normalizados e confiáveis, coletados por um \
sistema interno de inventário.

Regras obrigatórias:
- Para os itens de status ("security", "databases", "messaging", "main_technology",
  "sicredi_flow_usage", "object_storage", "containerization"), responda com um dos
  três valores em "status":
  "confirmado"      → o dado estruturado confirma diretamente
  "parcial"         → há indício mas não certeza total
  "nao_identificado" → nenhuma evidência encontrada nos dados
- Sempre cite no campo "detail" o dado exato que embasou a resposta
- É esperado e correto que vários itens sejam "nao_identificado" quando o dado
  estruturado simplesmente não contempla aquele item — não force uma resposta

Como localizar cada item nos dados estruturados fornecidos:
- "security": campo de autenticação (tipo e provedor)
- "databases": lista de bancos de dados
- "messaging": siga esta ORDEM DE PRIORIDADE, do sinal mais forte para o mais fraco —
  pare no primeiro que encontrar evidência:
  1. Nas integrações (consumidas ou consumidoras), procure algum item com
     "resource_type": "TOPIC" — sinal MAIS DIRETO possível, cite o resource_name
  2. Na autenticação de infraestrutura, procure entradas com "target": "KAFKA" ou
     mecanismo SASL associado a Kafka
  3. Em runtime.enabled_features, procure literalmente "KAFKA"
  4. SOMENTE se nenhum dos três sinais acima existir, procure endpoints cuja porta
     sugira um broker (porta 9093 é característica de Kafka) — heurística fraca; ao
     usá-la, marque no máximo "parcial", nunca "confirmado"
  Se nenhum dos quatro sinais existir, marque "nao_identificado"
- "main_technology": framework principal e lista de tecnologias declaradas
- "sicredi_flow_usage": procure por funcionalidades de plataforma habilitadas (ex:
  Consul, Vault, Kubernetes) — sinais diretos de uso da plataforma corporativa interna.
  Contas de automação responsáveis por deploys (ex: um "updated_by" que parece um
  usuário de sistema/bot) também são um sinal complementar
- "object_storage": procure evidência de QUALQUER serviço de armazenamento de objetos
  (AWS S3, Azure Blob Storage, Google Cloud Storage, ou equivalente interno)
- "containerization": procure no pipeline de deploy por ferramentas de build de imagem
  (ex: Jib) ou orquestração de containers (ex: Kubernetes)

Sobre o contrato OpenAPI: o texto fornecido já indica de forma confiável se o contrato
está preenchido ("sim"/"não") — use essa informação diretamente.

Sobre "component_type":
- Use o tipo de aplicação informado nos dados para classificar como
  "servico", "biblioteca", "batch" ou "modulo-compartilhado"

Distinção crítica — fato ausente vs. opinião técnica (não misture os dois campos):
- "detected_limitations": SOMENTE lacunas objetivas e verificáveis nos DADOS fornecidos
  (ex: "contrato OpenAPI não preenchido") — registro de fato, sem juízo de valor
- "improvement_suggestions": aqui SIM cabe julgamento técnico seu (ex: "considerar
  adicionar cache" é uma recomendação, não um fato observado)
- Não coloque a mesma informação nos dois campos com fraseado diferente
- Deixe "detected_limitations" como lista vazia [] se não houver nenhuma lacuna relevante

Regras de formato:
- Retorne APENAS um JSON válido — sem texto antes ou depois, sem blocos
  de código markdown"""


# (chave, orientação do campo "detail") dos 7 itens de status do checklist.
_ITENS_CHECKLIST = (
    ("security", "cite o tipo e provedor de autenticação encontrado"),
    ("databases", "cite os bancos de dados encontrados"),
    ("messaging", "cite qual dos 4 sinais (TOPIC / SASL-KAFKA / KAFKA em enabled_features / porta 9093) foi usado, ou a ausência de todos"),
    ("main_technology", "cite o framework principal encontrado"),
    ("sicredi_flow_usage", "cite as funcionalidades de plataforma (Consul, Vault, Kubernetes etc) encontradas"),
    ("object_storage", "identifique o provedor encontrado, ou a ausência de evidência"),
    ("containerization", "cite a evidência do pipeline de deploy encontrada"),
)


def montar_prompt_checklist_tecnico(document_context: dict[str, Any]) -> str:
    """Monta a mensagem do usuário para preencher o checklist técnico."""
    d = document_context
    ownership, quality, runtime, classification = (
        d.get(chave, {}) for chave in ("ownership", "quality", "runtime", "classification"))
    itens = ",\n".join(
        f'  "{chave}": {{\n    "status": "confirmado|parcial|nao_identificado",\n    "detail": "{detalhe}"\n  }}'
        for chave, detalhe in _ITENS_CHECKLIST
    )
    return f"""Analise os dados abaixo e preencha o checklist técnico deste componente.

{_formatar_document_context(d)}

## Checklist técnico — retorne EXATAMENTE este JSON preenchido

{{
  "component_name": "{d.get('component_name')}",
  "main_language": "{classification.get('main_language') or 'nao_identificado'}",
  "component_type": "servico|biblioteca|batch|modulo-compartilhado",
  "libraries": {_json(d.get('technology', {}).get('technologies', []))},
{itens},
  "detected_limitations": ["APENAS lacunas objetivas nos dados — lista vazia [] se não houver"],
  "tags": ["tags geradas com base na análise — mínimo 3"],
  "maturity_classification": "inicial|em-desenvolvimento|maduro|legado",
  "documentation_level": "inexistente|basico|intermediario|completo",
  "executive_summary": "resumo de 1-2 frases para exibição no catálogo",
  "improvement_suggestions": ["APENAS julgamento técnico/recomendações — até 3"],
  "team_id": {_json(ownership.get('team_id'))},
  "responsible_team": {_json(ownership.get('responsible_team'))},
  "project": {_json(ownership.get('project') or None)},
  "tribe": {_json(ownership.get('tribe', {}).get('name'))},
  "criticality": {_json(quality.get('criticality'))},
  "environment": {_json(runtime.get('resources_by_environment'))},
  "application_status": {_json(d.get('status'))},
  "application_category": {_json(classification.get('application_type'))}
}}"""