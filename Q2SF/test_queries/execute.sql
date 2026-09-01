select distinct
    q.Numero_da_Apolice__c,
    q.Proposta__c,
    q.Data_de_Emissao__c,
    q.Inicio_da_Vigencia__c,
    q.Termino_da_Vigencia__c,
    q.Premio_Quiver__c,
    sfo.OportunidadeApoliceAtual__c,
    sfo.Area_Formula__c,
    sfq.Cotacao__c,
    q.Status__c
from quiver as q
left join sf_opp as sfo
on q.Numero_da_Oportunidade__c = sfo.Numero_da_Oportunidade__c
left join sf_quote as sfq
on sfo.Numero_da_Oportunidade__c = sfq.Nome_Cotacao_Curto__c