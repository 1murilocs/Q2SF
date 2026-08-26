select
	td.Apolice as Numero_da_Apolice__c,
	left(td.Proposta, 6) as Proposta__c,
	datefromparts(year(td.Data_emissao), month(td.Data_emissao), day(td.Data_emissao)) AS Data_de_Emissao__c,
    datefromparts(year(td.Inicio_vigencia), month(td.Inicio_vigencia), day(td.Inicio_vigencia )) as Inicio_da_Vigencia__c,
	datefromparts(year(td.Termino_vigencia), month(td.Termino_vigencia), day(td.Termino_vigencia)) as Termino_da_Vigencia__c,
	td.Situacao as Status__c,
	left(td.Proposta_cia, 12) as Numero_da_Oportunidade__c,
	td.Premio_total as Premio_Quiver__c
from Tabela_Documentos td
join Tabela_Clientes tc
	on tc.Cliente = td.Cliente
join Tabela_Produtos tp
	on td.Produto = tp.Produto
join Tabela_Seguradoras ts
	on td.Seguradora = ts.Seguradora
where year(td.Inicio_vigencia) = year(getdate()) 
and td.Inicio_vigencia >= dateadd(day, -120, cast(getdate() as date))
and td.Inicio_vigencia <= cast(getdate() as date)
and td.Apolice is not null
and td.Proposta is not null
and td.Data_emissao is not null
and td.Inicio_vigencia is not null
and td.Termino_vigencia is not null
and td.Proposta_cia is not null
and trim(td.Endosso) = ''
and td.Proposta_cia like 'opo-%'
order by td.Inicio_vigencia desc;