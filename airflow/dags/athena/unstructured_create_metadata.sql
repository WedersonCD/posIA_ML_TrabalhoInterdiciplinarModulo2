CREATE EXTERNAL TABLE IF NOT EXISTS unstructured.metadata (
  tipo string,
  titulo string,
  titulos_alternativos string,
  autores string,
  resumo string,
  abstract_text string,
  palavras_chave string,
  cnpq string,
  idioma string,
  pais string,
  editor string,
  sigla_instituicao string,
  citacao string,
  tipo_acesso string,
  uri string,
  data_documento string,
  aparece_nas_colecoes string,
  id string,
  source_url string,
  pdf_url string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'case.insensitive' = 'false',

  'mapping.tipo' = 'Tipo',
  'mapping.titulo' = 'Título',
  'mapping.titulos_alternativos' = 'Título(s) alternativo(s)',
  'mapping.autores' = 'Autor(es)',
  'mapping.resumo' = 'Resumo',
  'mapping.abstract_text' = 'Abstract',
  'mapping.palavras_chave' = 'Palavras-chave',
  'mapping.cnpq' = 'CNPq',
  'mapping.idioma' = 'Idioma',
  'mapping.pais' = 'País',
  'mapping.editor' = 'Editor',
  'mapping.sigla_instituicao' = 'Sigla da Instituição',
  'mapping.citacao' = 'Citação',
  'mapping.tipo_acesso' = 'Tipo de Acesso',
  'mapping.uri' = 'URI',
  'mapping.data_documento' = 'Data do documento',
  'mapping.aparece_nas_colecoes' = 'Aparece nas coleções',
  'mapping.id' = '_id',
  'mapping.source_url' = '_source_url',
  'mapping.pdf_url' = '_pdf_url'
)
STORED AS TEXTFILE
LOCATION 's3://cluster-paper-ifg/Metadata/'
TBLPROPERTIES (
  'classification' = 'json'
);