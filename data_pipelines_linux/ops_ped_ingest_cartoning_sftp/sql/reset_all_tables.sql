-- =====================================================================
-- SCRIPT DE RESET COMPLETO: Vaciar todas las tablas + resetear IDENTITY
-- Base: OPS_OrquestaFact
-- ADVERTENCIA: Esto BORRA TODOS LOS DATOS. Usar solo en dev/testing.
-- =====================================================================
USE OPS_OrquestaFact;
GO

PRINT '============================================================';
PRINT '  RESET COMPLETO DE TABLAS EWM - ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '============================================================';
PRINT '';

-- =============================================
-- 1. TABLAS FINALES (vaciar primero por dependencias lógicas)
-- =============================================

-- Cartoning - Finales
PRINT '[1/22] Vaciando EWM_Items...';
TRUNCATE TABLE dbo.EWM_Items;
GO
PRINT '[2/22] Vaciando EWM_Cajas...';
TRUNCATE TABLE dbo.EWM_Cajas;
GO
PRINT '[3/22] Vaciando EWM_Pedidos...';
TRUNCATE TABLE dbo.EWM_Pedidos;
GO

-- WaveConfirm - Final
PRINT '[4/22] Vaciando EWM_WaveConfirm...';
TRUNCATE TABLE dbo.EWM_WaveConfirm;
GO

-- OutboundDelivery - Finales
PRINT '[5/22] Vaciando EWM_OutboundDelivery_Items...';
TRUNCATE TABLE dbo.EWM_OutboundDelivery_Items;
GO
PRINT '[6/22] Vaciando EWM_OutboundDelivery_Header...';
TRUNCATE TABLE dbo.EWM_OutboundDelivery_Header;
GO

-- OBDConfirm - Finales (6 tablas)
PRINT '[7/22] Vaciando EWM_OBDConfirm_Extensiones...';
TRUNCATE TABLE dbo.EWM_OBDConfirm_Extensiones;
GO
PRINT '[8/22] Vaciando EWM_OBDConfirm_Contenido_Embalaje...';
TRUNCATE TABLE dbo.EWM_OBDConfirm_Contenido_Embalaje;
GO
PRINT '[9/22] Vaciando EWM_OBDConfirm_Unidades_HDR...';
TRUNCATE TABLE dbo.EWM_OBDConfirm_Unidades_HDR;
GO
PRINT '[10/22] Vaciando EWM_OBDConfirm_Control_Posiciones...';
TRUNCATE TABLE dbo.EWM_OBDConfirm_Control_Posiciones;
GO
PRINT '[11/22] Vaciando EWM_OBDConfirm_Posiciones...';
TRUNCATE TABLE dbo.EWM_OBDConfirm_Posiciones;
GO
PRINT '[12/22] Vaciando EWM_OBDConfirm_Cabecera...';
TRUNCATE TABLE dbo.EWM_OBDConfirm_Cabecera;
GO

-- OBDConfirm - Hash de idempotencia
PRINT '[13/22] Vaciando EWM_OBDConfirm_FileHash...';
IF OBJECT_ID('dbo.EWM_OBDConfirm_FileHash', 'U') IS NOT NULL
    TRUNCATE TABLE dbo.EWM_OBDConfirm_FileHash;
GO

-- =============================================
-- 2. TABLAS STAGING (se vacían después de las finales)
-- =============================================

PRINT '[14/22] Vaciando Staging_EWM_Cartoning...';
TRUNCATE TABLE dbo.Staging_EWM_Cartoning;
GO
PRINT '[15/22] Vaciando Staging_EWM_WaveConfirm...';
TRUNCATE TABLE dbo.Staging_EWM_WaveConfirm;
GO
PRINT '[16/22] Vaciando Staging_EWM_OutboundDelivery_Header...';
TRUNCATE TABLE dbo.Staging_EWM_OutboundDelivery_Header;
GO
PRINT '[17/22] Vaciando Staging_EWM_OutboundDelivery_Items...';
TRUNCATE TABLE dbo.Staging_EWM_OutboundDelivery_Items;
GO
PRINT '[18/22] Vaciando Staging_EWM_OBDConfirm_Cabecera...';
TRUNCATE TABLE dbo.Staging_EWM_OBDConfirm_Cabecera;
GO
PRINT '[19/22] Vaciando Staging_EWM_OBDConfirm_Posiciones...';
TRUNCATE TABLE dbo.Staging_EWM_OBDConfirm_Posiciones;
GO
PRINT '[20/22] Vaciando Staging_EWM_OBDConfirm_Control_Posiciones...';
TRUNCATE TABLE dbo.Staging_EWM_OBDConfirm_Control_Posiciones;
GO
PRINT '[21/22] Vaciando Staging_EWM_OBDConfirm_Unidades_HDR...';
TRUNCATE TABLE dbo.Staging_EWM_OBDConfirm_Unidades_HDR;
GO
PRINT '[22/22] Vaciando Staging_EWM_OBDConfirm_Contenido_Embalaje...';
TRUNCATE TABLE dbo.Staging_EWM_OBDConfirm_Contenido_Embalaje;
GO
PRINT '[23/22] Vaciando Staging_EWM_OBDConfirm_Extensiones...';
TRUNCATE TABLE dbo.Staging_EWM_OBDConfirm_Extensiones;
GO

-- =============================================
-- 3. BITÁCORA
-- =============================================
PRINT '[24/24] Vaciando BitacoraArchivos...';
TRUNCATE TABLE dbo.BitacoraArchivos;
GO

-- =============================================
-- 4. VERIFICACIÓN FINAL
-- =============================================
PRINT '';
PRINT '============================================================';
PRINT '  VERIFICACION - Conteo de registros post-reset';
PRINT '============================================================';

SELECT 'BitacoraArchivos' AS Tabla, COUNT(*) AS Registros FROM dbo.BitacoraArchivos
UNION ALL SELECT 'Staging_EWM_Cartoning', COUNT(*) FROM dbo.Staging_EWM_Cartoning
UNION ALL SELECT 'Staging_EWM_WaveConfirm', COUNT(*) FROM dbo.Staging_EWM_WaveConfirm
UNION ALL SELECT 'Staging_EWM_OutboundDelivery_Header', COUNT(*) FROM dbo.Staging_EWM_OutboundDelivery_Header
UNION ALL SELECT 'Staging_EWM_OutboundDelivery_Items', COUNT(*) FROM dbo.Staging_EWM_OutboundDelivery_Items
UNION ALL SELECT 'Staging_EWM_OBDConfirm_Cabecera', COUNT(*) FROM dbo.Staging_EWM_OBDConfirm_Cabecera
UNION ALL SELECT 'Staging_EWM_OBDConfirm_Posiciones', COUNT(*) FROM dbo.Staging_EWM_OBDConfirm_Posiciones
UNION ALL SELECT 'Staging_EWM_OBDConfirm_Control_Posiciones', COUNT(*) FROM dbo.Staging_EWM_OBDConfirm_Control_Posiciones
UNION ALL SELECT 'Staging_EWM_OBDConfirm_Unidades_HDR', COUNT(*) FROM dbo.Staging_EWM_OBDConfirm_Unidades_HDR
UNION ALL SELECT 'Staging_EWM_OBDConfirm_Contenido_Embalaje', COUNT(*) FROM dbo.Staging_EWM_OBDConfirm_Contenido_Embalaje
UNION ALL SELECT 'Staging_EWM_OBDConfirm_Extensiones', COUNT(*) FROM dbo.Staging_EWM_OBDConfirm_Extensiones
UNION ALL SELECT 'EWM_Pedidos', COUNT(*) FROM dbo.EWM_Pedidos
UNION ALL SELECT 'EWM_Cajas', COUNT(*) FROM dbo.EWM_Cajas
UNION ALL SELECT 'EWM_Items', COUNT(*) FROM dbo.EWM_Items
UNION ALL SELECT 'EWM_WaveConfirm', COUNT(*) FROM dbo.EWM_WaveConfirm
UNION ALL SELECT 'EWM_OutboundDelivery_Header', COUNT(*) FROM dbo.EWM_OutboundDelivery_Header
UNION ALL SELECT 'EWM_OutboundDelivery_Items', COUNT(*) FROM dbo.EWM_OutboundDelivery_Items
UNION ALL SELECT 'EWM_OBDConfirm_Cabecera', COUNT(*) FROM dbo.EWM_OBDConfirm_Cabecera
UNION ALL SELECT 'EWM_OBDConfirm_Posiciones', COUNT(*) FROM dbo.EWM_OBDConfirm_Posiciones
UNION ALL SELECT 'EWM_OBDConfirm_Control_Posiciones', COUNT(*) FROM dbo.EWM_OBDConfirm_Control_Posiciones
UNION ALL SELECT 'EWM_OBDConfirm_Unidades_HDR', COUNT(*) FROM dbo.EWM_OBDConfirm_Unidades_HDR
UNION ALL SELECT 'EWM_OBDConfirm_Contenido_Embalaje', COUNT(*) FROM dbo.EWM_OBDConfirm_Contenido_Embalaje
UNION ALL SELECT 'EWM_OBDConfirm_Extensiones', COUNT(*) FROM dbo.EWM_OBDConfirm_Extensiones
ORDER BY Tabla;
GO

PRINT '';
PRINT '============================================================';
PRINT '  RESET COMPLETADO - ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '  IMPORTANTE: Borrar state_store.json para reprocesar archivos';
PRINT '============================================================';
GO
